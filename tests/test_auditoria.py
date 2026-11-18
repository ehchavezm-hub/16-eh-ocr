"""Regresiones de la auditoría: cada prueba corresponde a una no conformidad corregida."""

from __future__ import annotations

from eh_ocr import salidas
from eh_ocr.modelo import EstadoPagina, Linea, Palabra, PerfilPagina, ResultadoDocumento, ResultadoPagina, TipoPagina


def _resultado(tmp_path, textos, nombre="doc.png"):
    palabras = [Palabra(t, 0.99, (100 + 300 * i, 100, 350 + 300 * i, 140)) for i, t in enumerate(textos)]
    perfil = PerfilPagina(1, TipoPagina.ESCANEO, 2480, 3508, 300, 595, 842)
    return ResultadoDocumento(str(tmp_path / nombre),
                              [ResultadoPagina(perfil, [Linea(palabras)], EstadoPagina.OK, ["RapidOCR"], 0.99, 1.0)])


def test_caracteres_de_control_no_rompen_word_ni_excel(tmp_path):
    r = _resultado(tmp_path, ["Total\x0c", "\x00S/", "1\x0b200"])
    errores: list[str] = []
    rutas = salidas.generar(r, ("docx", "xlsx"), tmp_path, errores=errores)
    assert errores == [] and len(rutas) == 2


def test_excel_nunca_crea_formulas_desde_el_documento(tmp_path):
    from openpyxl import load_workbook

    r = _resultado(tmp_path, ['=HYPERLINK("http://x","clic")'])
    xlsx = salidas.generar(r, ("xlsx",), tmp_path)[0]
    celda = load_workbook(xlsx)["Página 1"]["A1"]
    assert celda.data_type == "s"


def test_pdf_buscable_conserva_caracteres_especiales(tmp_path):
    import pdfplumber
    from PIL import Image

    origen = tmp_path / "doc.png"
    Image.new("RGB", (2480, 3508), "white").save(origen, dpi=(300, 300))
    r = _resultado(tmp_path, ["Monto:", "€ 1 200", "—", "“firmado”"])
    pdf = salidas.generar(r, ("pdf",), tmp_path)[0]
    texto = pdfplumber.open(pdf).pages[0].extract_text()
    for esperado in ("€", "—", "“firmado”"):
        assert esperado in texto


def test_no_se_reprocesan_los_resultados(tmp_path):
    from eh_ocr.documento import listar_archivos

    for nombre in ("contrato.pdf", "contrato_ocr.pdf", "contrato_ocr (2).pdf", "informe_ocr.docx", "foto.jpg"):
        (tmp_path / nombre).write_bytes(b"x")
    nombres = [p.name for p in listar_archivos([tmp_path])]
    assert nombres == ["contrato.pdf", "foto.jpg"]


def test_texto_digital_ilegible_se_detecta():
    from eh_ocr.pipeline import texto_digital_legible

    def ps(textos):
        return [Palabra(t, 1.0, (0, 0, 1, 1)) for t in textos]

    assert texto_digital_legible(ps(["El", "contratista", "entregará", "la", "obra", "en", "plazo"] * 6))
    assert not texto_digital_legible(ps(["(cid:12)(cid:7)", "(cid:3)"] * 20))
    assert not texto_digital_legible(ps(["Xqzt", "Vbbrn", "Kjjwq", "Plrrm", "Zzxqv"] * 10))


def test_carpeta_de_datos_con_respaldo(tmp_path, monkeypatch):
    from eh_ocr import config

    bloqueada = tmp_path / "solo_lectura"
    monkeypatch.delenv("EH_OCR_DATOS", raising=False)
    monkeypatch.setattr(config, "_datos_cache", None)
    monkeypatch.setattr(config, "carpeta_base", lambda: bloqueada)
    monkeypatch.setattr(config, "_escribible", lambda ruta: ruta != bloqueada / "datos" and (ruta.mkdir(parents=True, exist_ok=True) or True))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert config.carpeta_datos() == tmp_path / "local" / "eh-ocr" / "datos"


def test_tiff_multipagina_se_lee_por_partes(tmp_path):
    from PIL import Image

    from eh_ocr.documento import Documento

    ruta = tmp_path / "lote.tif"
    paginas = [Image.new("RGB", (800, 1100), c) for c in ("white", "gray", "black")]
    paginas[0].save(ruta, save_all=True, append_images=paginas[1:], dpi=(150, 150))
    with Documento(ruta) as doc:
        assert len(doc) == 3
        assert not hasattr(doc, "_frames")  # no se guardan todas las páginas en memoria
        img, dpi = doc.pagina(2).imagen()
        assert img[0, 0, 0] == 0 and dpi == 150
        ancho, alto = doc.pagina(1).tamano_pt()
        assert round(ancho) == 384 and round(alto) == 528


def _linea(texto, x, y, ancho):
    palabras = texto.split()
    paso = ancho / len(palabras)
    return [Palabra(w, 0.99, (x + i * paso, y, x + (i + 1) * paso - 10, y + 30)) for i, w in enumerate(palabras)]


def test_dos_columnas_se_leen_en_orden():
    from eh_ocr.votacion import agrupar_en_lineas

    palabras = _linea("TITULO DEL CONTRATO QUE CRUZA AMBAS COLUMNAS", 100, 50, 2200)
    for i in range(8):
        palabras += _linea(f"izquierda renglon {i} texto corrido", 100, 150 + i * 50, 1000)
        palabras += _linea(f"derecha renglon {i} texto corrido", 1300, 150 + i * 50, 1000)
    lineas = agrupar_en_lineas(palabras)
    textos = [l.texto for l in lineas]
    assert textos[0].startswith("TITULO")
    assert textos[1:9] == [f"izquierda renglon {i} texto corrido" for i in range(8)]
    assert textos[9:17] == [f"derecha renglon {i} texto corrido" for i in range(8)]


def test_una_tabla_no_se_confunde_con_dos_columnas():
    from eh_ocr.votacion import agrupar_en_lineas

    palabras = []
    for i in range(12):
        palabras += [Palabra(f"partida{i}", 0.99, (100, 100 + i * 50, 300, 130 + i * 50)),
                     Palabra(f"{i}0.00", 0.99, (1900, 100 + i * 50, 2050, 130 + i * 50))]
    textos = [l.texto for l in agrupar_en_lineas(palabras)]
    assert textos[:2] == ["partida0", "00.00"]  # fila a fila, sin reordenar por columnas


def test_pdf_de_imagen_liviano(tmp_path):
    """Una foto color de 300 ppp: el PDF buscable no debe pesar varias veces más que la imagen."""
    import numpy as np
    from PIL import Image

    origen = tmp_path / "foto.png"
    rng = np.random.default_rng(0)
    base = np.full((3508, 2480, 3), 235, np.uint8)
    base[::40] = 30
    base += rng.integers(0, 12, base.shape, dtype=np.uint8)
    Image.fromarray(base).save(origen, dpi=(300, 300))
    r = _resultado(tmp_path, ["texto"], nombre="foto.png")
    pdf = salidas.generar(r, ("pdf",), tmp_path)[0]
    assert pdf.stat().st_size < 2_500_000


def test_limpieza_de_trabajos_viejos(tmp_path):
    import os
    import time

    from eh_ocr import config
    from eh_ocr.pipeline import limpiar_cache

    viejo = config.carpeta_datos() / "trabajos" / "viejo"
    nuevo = config.carpeta_datos() / "trabajos" / "nuevo"
    for d in (viejo, nuevo):
        d.mkdir(parents=True)
        (d / "p00001.json").write_text("{}")
    hace_40_dias = time.time() - 40 * 86400
    os.utime(viejo / "p00001.json", (hace_40_dias, hace_40_dias))
    assert limpiar_cache(30) == 1
    assert not viejo.exists() and nuevo.exists()


def test_cache_se_invalida_si_cambian_los_motores(tmp_path, monkeypatch):
    """Regresión: una página leída sin Tesseract se reutilizaba aunque luego Tesseract estuviera listo."""
    from eh_ocr import pipeline

    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF")
    monkeypatch.setattr(pipeline, "firma_motores", lambda: "rapid=small|tess=False")
    antes = pipeline.id_trabajo(doc)
    monkeypatch.setattr(pipeline, "firma_motores", lambda: "rapid=medium|tess=True")
    assert pipeline.id_trabajo(doc) != antes


def test_pagina_lenta_se_relee_en_modo_rapido(escaneo, monkeypatch):
    """Regresión: con todos los motores, páginas densas superaban el límite y quedaban «no procesadas»."""
    import time

    from eh_ocr import config, pipeline

    original = pipeline.procesar_pagina

    def lenta(pagina, motores, lector, rapido=False):
        if not rapido:
            time.sleep(3)  # simula una página que tarda demasiado
        return original(pagina, motores, lector, rapido)

    monkeypatch.setattr(pipeline, "procesar_pagina", lenta)
    monkeypatch.setattr(config, "TIEMPO_LIMITE_BASE_S", 1)
    p = pipeline.procesar_documento(escaneo).paginas[0]
    assert p.estado != EstadoPagina.NO_PROCESADA
    assert "modo rápido" in p.mensaje
    assert "representantes" in p.texto


def test_directml_usa_una_sola_instancia(monkeypatch):
    """Regresión: varias sesiones DirectML a la vez hicieron caer el controlador de NVIDIA."""
    from eh_ocr.motores.rapid import MotorRapid

    m = MotorRapid()
    m.acelerador = "DirectML"
    assert m.instancias_maximas() == 1


def test_proteccion_de_caidas_activa_modo_seguro(monkeypatch):
    import atexit

    from eh_ocr import __main__ as principal
    from eh_ocr import config

    monkeypatch.delenv("EH_OCR_SOLO_CPU", raising=False)
    monkeypatch.setattr(atexit, "register", lambda f: None)  # simula que la sesión no cerró bien
    assert principal._proteccion_caidas() is False  # primera vez: normal
    assert principal._proteccion_caidas() is True   # la marca quedó: modo seguro
    import os

    assert os.environ["EH_OCR_SOLO_CPU"] == "1"
    (config.carpeta_datos() / "sesion_abierta").unlink()
    monkeypatch.delenv("EH_OCR_SOLO_CPU")


def test_error_de_la_grafica_pasa_al_procesador(escaneo):
    """Si DirectML lanza un error, la página se lee igual con el procesador."""
    import numpy as np

    from eh_ocr.motores.rapid import MotorRapid

    m = MotorRapid()
    m._cargar()

    class GraficaRota:
        def __call__(self, *_a, **_k):
            raise RuntimeError("UnicodeDecodeError del controlador")

    m._libres.get_nowait()
    m._libres.put(GraficaRota())
    m.acelerador = "DirectML"
    img = np.full((200, 600, 3), 255, np.uint8)
    m.reconocer(img)  # no debe lanzar
    assert m.acelerador == "CPU"


def test_votacion_conserva_dos_columnas():
    """Regresión: con Tesseract, la votación reordenaba solo de arriba abajo y mezclaba columnas."""
    from eh_ocr.votacion import votar

    palabras = _linea("TITULO DEL CONTRATO QUE CRUZA AMBAS COLUMNAS", 100, 50, 2200)
    for i in range(8):
        palabras += _linea(f"izquierda renglon {i} texto corrido", 100, 150 + i * 50, 1000)
        palabras += _linea(f"derecha renglon {i} texto corrido", 1300, 150 + i * 50, 1000)
    import copy

    textos = [l.texto for l in votar(copy.deepcopy(palabras), copy.deepcopy(palabras))]
    assert textos[1:9] == [f"izquierda renglon {i} texto corrido" for i in range(8)]


def test_tras_una_caida_se_queda_en_procesador(monkeypatch):
    import atexit
    import os

    from eh_ocr import __main__ as principal
    from eh_ocr import config

    monkeypatch.delenv("EH_OCR_SOLO_CPU", raising=False)
    monkeypatch.setattr(atexit, "register", lambda f: None)
    principal._proteccion_caidas()            # sesión que "se cae" (la marca queda)
    principal._proteccion_caidas()            # siguiente: detecta la caída
    (config.carpeta_datos() / "sesion_abierta").unlink()
    monkeypatch.delenv("EH_OCR_SOLO_CPU")
    assert principal._proteccion_caidas() is True  # y las siguientes siguen en CPU
    assert os.environ["EH_OCR_SOLO_CPU"] == "1"
    monkeypatch.delenv("EH_OCR_SOLO_CPU")
