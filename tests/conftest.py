from __future__ import annotations

import glob
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

TEXTO_ES = [
    "ACTA DE REUNIÓN NÚMERO 14",
    "En la ciudad de Lima se reunieron los representantes",
    "de ambas partes para revisar el avance del proyecto.",
    "Primero: se aprueba el modelo de cronograma presentado,",
    "con un plazo de ejecución de 120 días calendario.",
]
TEXTO_DE = ["Die Größe der Brücke überrascht über 50 Männer."]
TEXTO_EN = ["The quick brown fox jumps over the lazy dog 2026."]
TEXTO = TEXTO_ES + TEXTO_DE + TEXTO_EN


def fuente(tam: int) -> ImageFont.FreeTypeFont:
    for patron in ("/usr/share/fonts/**/DejaVuSerif.ttf", "C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/arial.ttf"):
        encontrados = glob.glob(patron, recursive=True)
        if encontrados:
            return ImageFont.truetype(encontrados[0], tam)
    return ImageFont.load_default(tam)


def pagina_escaneada(lineas=TEXTO, inclinacion=0.0, dpi=300, ruido=False) -> Image.Image:
    escala = dpi / 300
    w, h = int(2480 * escala), int(3508 * escala)
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    f = fuente(int(40 * escala))
    for i, l in enumerate(lineas):
        d.text((int(200 * escala), int((300 + i * 90) * escala)), l, font=f, fill="black")
    if inclinacion:
        im = im.rotate(inclinacion, fillcolor="white")
    if ruido:
        import numpy as np

        arr = np.asarray(im).astype("int16")
        rng = np.random.default_rng(1)
        arr = np.clip(arr + rng.normal(0, 25, arr.shape), 0, 255).astype("uint8")
        im = Image.fromarray(arr)
    return im


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    monkeypatch.setenv("EH_OCR_DATOS", str(tmp_path / "datos"))
    yield


@pytest.fixture
def escaneo(tmp_path) -> Path:
    ruta = tmp_path / "escaneo.png"
    pagina_escaneada(inclinacion=2.0).save(ruta, dpi=(300, 300))
    return ruta


@pytest.fixture
def pdf_digital(tmp_path) -> Path:
    from reportlab.pdfgen import canvas

    ruta = tmp_path / "digital.pdf"
    c = canvas.Canvas(str(ruta))
    y = 780
    for l in TEXTO:
        c.drawString(72, y, l.encode("latin-1", "replace").decode("latin-1"))
        y -= 20
    c.showPage()
    c.save()
    return ruta


@pytest.fixture
def pdf_escaneado(tmp_path) -> Path:
    """PDF de 2 páginas que son imágenes (como sale de un escáner)."""
    ruta = tmp_path / "escaneado.pdf"
    p1 = pagina_escaneada(inclinacion=-1.5)
    p2 = pagina_escaneada(lineas=TEXTO_EN * 3)
    p1.save(ruta, save_all=True, append_images=[p2], resolution=300)
    return ruta


def cer(referencia: str, hipotesis: str) -> float:
    from eh_ocr.metricas import cer as _cer

    return _cer(referencia, hipotesis)


requiere_tesseract = pytest.mark.skipif(
    __import__("shutil").which("tesseract") is None and not os.environ.get("EH_OCR_TESSERACT_INCLUIDO"),
    reason="Tesseract no instalado",
)


@pytest.fixture
def foto(tmp_path) -> Path:
    """Foto de celular simulada: hoja en perspectiva, fondo de mesa y sombra lateral."""
    import cv2
    import numpy as np

    hoja = np.asarray(pagina_escaneada().resize((1240, 1754)))
    alto, ancho = 2400, 1800
    fondo = np.full((alto, ancho, 3), (90, 70, 50), np.uint8)
    src = np.float32([[0, 0], [1240, 0], [1240, 1754], [0, 1754]])
    dst = np.float32([[260, 180], [1560, 260], [1640, 2200], [140, 2120]])
    M = cv2.getPerspectiveTransform(src, dst)
    warp = cv2.warpPerspective(hoja, M, (ancho, alto))
    mascara = cv2.warpPerspective(np.full(hoja.shape[:2], 255, np.uint8), M, (ancho, alto))
    img = np.where(mascara[..., None] > 0, warp, fondo).astype(np.float32)
    img = np.clip(img * np.linspace(1.0, 0.55, ancho)[None, :, None], 0, 255).astype(np.uint8)
    ruta = tmp_path / "foto.jpg"
    cv2.imwrite(str(ruta), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return ruta
