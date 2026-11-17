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


def test_celdas_superpuestas_no_rompen_excel_ni_word(tmp_path):
    """Regresión: una celda en «L» se superponía con otra y Excel fallaba ('value' is read-only)."""
    from eh_ocr.modelo import EstadoPagina, Linea, Palabra, PerfilPagina, ResultadoDocumento, ResultadoPagina, TipoPagina
    from eh_ocr.tablas import Celda, Tabla, asignar_palabras, normalizar

    palabras = [Palabra(t, 0.99, (x, y, x + 80, y + 30)) for t, x, y in
                [("A", 10, 10), ("B", 210, 10), ("C", 10, 110), ("D", 210, 110), ("E", 410, 110)]]
    t = Tabla((0, 0, 600, 200), 2, 3, [
        Celda(0, 0, 2, 2, (0, 0, 400, 200)),   # 2x2 que se superpone con las siguientes
        Celda(0, 1, 1, 2, (200, 0, 600, 100)),
        Celda(1, 2, 1, 1, (400, 100, 600, 200)),
        Celda(5, 5, 1, 1, (0, 0, 1, 1)),        # fuera de la tabla
    ], "bordes")
    normalizar(t)
    asignar_palabras(t, palabras)
    ocupadas = [(c.fila + r, c.col + k) for c in t.celdas for r in range(c.filas) for k in range(c.cols)]
    assert len(ocupadas) == len(set(ocupadas))  # sin superposiciones
    assert all(c.fila + c.filas <= 2 and c.col + c.cols <= 3 for c in t.celdas)

    perfil = PerfilPagina(1, TipoPagina.ESCANEO, 600, 200, 300, 144, 48)
    r = ResultadoDocumento(str(tmp_path / "doc.png"),
                           [ResultadoPagina(perfil, [Linea(palabras)], EstadoPagina.OK, ["RapidOCR"], 0.99, 1.0, tablas=[t])])
    errores: list[str] = []
    rutas = salidas.generar(r, ("xlsx", "docx"), tmp_path, errores=errores)
    assert errores == [] and len(rutas) == 2


def test_un_formato_que_falla_no_impide_los_demas(tmp_path, monkeypatch):
    from eh_ocr.modelo import EstadoPagina, Linea, Palabra, PerfilPagina, ResultadoDocumento, ResultadoPagina, TipoPagina
    from eh_ocr.salidas import xlsx_salida

    def falla(*_a, **_k):
        raise RuntimeError("prueba")

    monkeypatch.setattr(xlsx_salida, "escribir", falla)
    perfil = PerfilPagina(1, TipoPagina.ESCANEO, 600, 200, 300, 144, 48)
    r = ResultadoDocumento(str(tmp_path / "doc.png"),
                           [ResultadoPagina(perfil, [Linea([Palabra("hola", 0.99, (0, 0, 50, 20))])], EstadoPagina.OK, [], 0.99, 1.0)])
    errores: list[str] = []
    rutas = salidas.generar(r, ("txt", "xlsx", "docx"), tmp_path, errores=errores)
    assert [p.suffix for p in rutas] == [".txt", ".docx"]
    assert errores and "Excel" in errores[0]
    assert not list(tmp_path.glob("*.xlsx"))  # nada a medias en disco


def test_se_elige_la_estructura_que_no_junta_columnas():
    """Regresión (CI): el modelo juntó «Mes» y «Avance» en una celda; gana la alineación."""
    from eh_ocr.modelo import Palabra
    from eh_ocr.tablas import Celda, Tabla, _mejor_candidato

    palabras = []
    for r, fila in enumerate([["Mes", "Avance", "Monto"], ["Enero", "12", "45,000"], ["Marzo", "40", "150,000"]]):
        for c, t in enumerate(fila):
            x, y = 100 + c * 700, 100 + r * 80
            palabras.append(Palabra(t, 0.99, (x, y, x + 150, y + 40)))
    juntadas = Tabla((0, 0, 2200, 340), 3, 2, [
        Celda(r, 0, 1, 1, (0, 60 + r * 80, 1100, 140 + r * 80)) for r in range(3)] + [
        Celda(r, 1, 1, 1, (1100, 60 + r * 80, 2200, 140 + r * 80)) for r in range(3)], "modelo")
    separadas = Tabla((0, 0, 2200, 340), 3, 3, [
        Celda(r, c, 1, 1, (c * 700 + 50, 60 + r * 80, c * 700 + 750, 140 + r * 80)) for r in range(3) for c in range(3)],
        "alineacion")
    assert _mejor_candidato([juntadas, separadas], palabras) is separadas
