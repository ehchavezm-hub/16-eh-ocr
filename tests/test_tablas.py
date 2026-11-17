"""Tablas: detección, celdas combinadas y salidas Word/Excel/Markdown/TXT."""

from __future__ import annotations

import pytest
from docx import Document as Docx
from openpyxl import load_workbook

from eh_ocr import salidas
from eh_ocr.pipeline import procesar_documento
from eh_ocr.red import bloquear_red, desbloquear_red
from eh_ocr.tablas import texto_celda

from .conftest import requiere_tesseract


@pytest.fixture(autouse=True)
def sin_red():
    bloquear_red()
    yield
    desbloquear_red()


def _celdas(tabla, palabras):
    return {(c.fila, c.col): (texto_celda(c, palabras), c.filas, c.cols) for c in tabla.celdas}


@requiere_tesseract
def test_tabla_escaneada_con_bordes(tabla_escaneada, tmp_path):
    r = procesar_documento(tabla_escaneada)
    p = r.paginas[0]
    assert len(p.tablas) == 1
    t = p.tablas[0]
    assert (t.n_filas, t.n_cols, t.metodo) == (5, 4, "bordes")
    c = _celdas(t, p.palabras)
    assert c[(0, 2)][0] == "Metrado"
    assert c[(1, 0)][0] == "Excavación masiva"
    assert c[(3, 0)][0] == "Acero de refuerzo corrugado grado 60"  # celda de 2 renglones
    assert c[(4, 0)] == ("TOTAL COSTO DIRECTO", 1, 3)  # celda combinada
    assert c[(4, 3)][0] == "75,256.00"
    # el texto fuera de la tabla sigue como texto, en orden
    tipos = [tipo for tipo, _ in p.bloques()]
    assert tipos == ["linea", "linea", "tabla", "linea"]

    pdf, docx, xlsx, txt, md = salidas.generar(r, ("pdf", "docx", "xlsx", "txt", "md"), tmp_path / "out")
    tabla_word = Docx(docx).tables[0]
    assert len(tabla_word.rows) == 5 and len(tabla_word.columns) == 4
    assert tabla_word.cell(3, 0).text == "Acero de refuerzo corrugado grado 60"
    assert tabla_word.cell(4, 0).text == tabla_word.cell(4, 2).text == "TOTAL COSTO DIRECTO"

    hoja = load_workbook(xlsx)["Página 1"]
    fila_tabla = next(r for r in range(1, 10) if hoja.cell(r, 1).value == "Partida")
    assert hoja.cell(fila_tabla + 1, 3).value == 320  # número real, se puede sumar
    assert hoja.cell(fila_tabla + 3, 3).value == 5200
    rangos = [str(m) for m in hoja.merged_cells.ranges]
    assert f"A{fila_tabla + 4}:C{fila_tabla + 4}" in rangos

    assert "Partida\tUnd.\tMetrado\tPrecio" in txt.read_text(encoding="utf-8")
    assert "| Partida | Und. | Metrado | Precio |" in md.read_text(encoding="utf-8")


def test_tabla_pdf_digital(pdf_digital_con_tabla, tmp_path):
    r = procesar_documento(pdf_digital_con_tabla)
    p = r.paginas[0]
    assert len(p.tablas) == 1
    t = p.tablas[0]
    assert (t.n_filas, t.n_cols, t.metodo) == (5, 4, "pdf")
    c = _celdas(t, p.palabras)
    assert c[(0, 0)][0] == "Partida"
    assert c[(3, 2)][0] == "5,200.00"
    assert c[(4, 0)] == ("TOTAL COSTO DIRECTO", 1, 3)
    xlsx = salidas.generar(r, ("xlsx",), tmp_path / "out")[0]
    hoja = load_workbook(xlsx)["Página 1"]
    valores = [[c.value for c in fila] for fila in hoja.iter_rows()]
    assert ["Partida", "Und.", "Metrado", "Precio"] in valores


@requiere_tesseract
def test_tabla_sin_bordes(tmp_path):
    """Detectada por el modelo de zonas; estructura por SLANet+ (si está incluido) o por alineación."""
    from PIL import Image, ImageDraw

    from eh_ocr import config
    from eh_ocr.tablas import ModelosTablas

    from .conftest import fuente

    f = fuente(34)
    im = Image.new("RGB", (2480, 3508), "white")
    d = ImageDraw.Draw(im)
    d.text((200, 250), "Cronograma de valorizaciones del proyecto", font=f, fill="black")
    filas = [["Mes", "Avance", "Monto"], ["Enero", "12 %", "45,000.00"], ["Febrero", "25 %", "93,750.00"],
             ["Marzo", "40 %", "150,000.00"], ["Abril", "60 %", "225,000.00"]]
    for r, fila in enumerate(filas):
        for c, t in enumerate(fila):
            d.text((200 + c * 700, 420 + r * 80), t, font=f, fill="black")
    d.line([(200, 470), (2200, 470)], fill="black", width=3)
    d.text((200, 900), "Las valorizaciones se presentan el último día hábil de cada mes.", font=f, fill="black")
    ruta = tmp_path / "cronograma.png"
    im.save(ruta, dpi=(300, 300))

    if (config.carpeta_modelos() / "tablas" / "slanet-plus.onnx").exists():
        assert ModelosTablas.obtener().estado["estructura"]

    p = procesar_documento(ruta).paginas[0]
    assert len(p.tablas) == 1
    t = p.tablas[0]
    assert t.n_cols == 3
    textos = {texto_celda(c, p.palabras) for c in t.celdas}
    for esperado in ("Mes", "Febrero", "93,750.00", "60 %"):
        assert esperado in textos
    assert [tipo for tipo, _ in p.bloques()] == ["linea", "tabla", "linea"]
