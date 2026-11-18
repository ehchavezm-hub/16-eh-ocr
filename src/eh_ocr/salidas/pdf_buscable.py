"""PDF con texto buscable (pikepdf MPL + reportlab BSD; sin PyMuPDF ni Ghostscript).

- PDF de origen: se conserva cada página tal cual y se superpone una capa
  de texto invisible en las páginas reconocidas por OCR. Las páginas que ya
  tenían texto digital no se tocan.
- Imagen de origen: se crea una página con la imagen y la capa de texto.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..archivos import escribir_atomico
from ..documento import Documento
from ..modelo import EstadoPagina, ResultadoDocumento, ResultadoPagina, TipoPagina

_FUENTE_UNICODE = "EhOcrDejaVu"
FUENTE = "Helvetica"


def _fuente() -> str:
    """DejaVu Sans incluida (cubre €, —, comillas tipográficas…); Helvetica si faltara."""
    global FUENTE
    if FUENTE == _FUENTE_UNICODE:
        return FUENTE
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from .. import config

    ruta = config.carpeta_recursos() / "fuentes" / "DejaVuSans.ttf"
    if ruta.exists():
        try:
            pdfmetrics.registerFont(TTFont(_FUENTE_UNICODE, str(ruta)))
            FUENTE = _FUENTE_UNICODE
        except Exception:
            pass
    return FUENTE


def _texto_seguro(t: str) -> str:
    if _fuente() == _FUENTE_UNICODE:
        return t
    # Helvetica estándar solo cubre Latin-1
    return "".join(c if ord(c) < 256 else "?" for c in t)


def _dibujar_capa_texto(c: canvas.Canvas, r: ResultadoPagina, ancho_pt: float, alto_pt: float) -> None:
    perfil = r.perfil
    if not perfil.ancho_px or not perfil.alto_px:
        return
    sx = ancho_pt / perfil.ancho_px
    sy = alto_pt / perfil.alto_px
    fuente = _fuente()
    ancho_espacio = stringWidth(" ", fuente, 10) / 10
    for linea in r.lineas:
        palabras = linea.palabras
        for k, w in enumerate(palabras):
            x0, y0, x1, y1 = w.caja
            alto = max((y1 - y0) * sy, 1.0)
            ancho = max((x1 - x0) * sx, 1.0)
            texto = _texto_seguro(w.texto)
            tam = alto * 0.85
            t = c.beginText()
            t.setTextRenderMode(3)  # invisible
            t.setFont(fuente, tam)
            ancho_natural = stringWidth(texto, fuente, tam) or 1.0
            t.setHorizScale(100.0 * ancho / ancho_natural)
            t.setTextOrigin(x0 * sx, alto_pt - y1 * sy + alto * 0.15)
            t.textOut(texto)
            # Un espacio real que ocupa el hueco hasta la siguiente palabra:
            # así los lectores de PDF separan bien las palabras al copiar o buscar.
            if k + 1 < len(palabras):
                hueco = (palabras[k + 1].caja[0] - x1) * sx
                if hueco > 0:
                    t.setHorizScale(100.0 * hueco / (ancho_espacio * tam))
                    t.textOut(" ")
            c.drawText(t)


def _capa_pdf(r: ResultadoPagina, ancho_pt: float, alto_pt: float, rotacion: int = 0) -> bytes:
    """Capa de texto en el espacio NO rotado de la página (ancho/alto del mediabox).

    El texto se ubica en coordenadas visibles y se transforma según /Rotate.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho_pt, alto_pt))
    vis_w, vis_h = (alto_pt, ancho_pt) if rotacion in (90, 270) else (ancho_pt, alto_pt)
    if rotacion == 90:
        c.transform(0, 1, -1, 0, ancho_pt, 0)
    elif rotacion == 180:
        c.transform(-1, 0, 0, -1, ancho_pt, alto_pt)
    elif rotacion == 270:
        c.transform(0, -1, 1, 0, 0, alto_pt)
    _dibujar_capa_texto(c, r, vis_w, vis_h)
    c.showPage()
    c.save()
    return buf.getvalue()


def _necesita_capa(r: ResultadoPagina) -> bool:
    return r.estado != EstadoPagina.NO_PROCESADA and r.perfil.tipo != TipoPagina.DIGITAL and bool(r.lineas)


def escribir(resultado: ResultadoDocumento, destino: Path, contrasena: str | None = None) -> None:
    origen = Path(resultado.origen)
    if origen.suffix.lower() == ".pdf":
        _desde_pdf(resultado, origen, destino, contrasena)
    else:
        _desde_imagen(resultado, origen, destino)


def _desde_pdf(resultado: ResultadoDocumento, origen: Path, destino: Path, contrasena: str | None) -> None:
    with pikepdf.open(origen, password=contrasena or "") as pdf:
        for r in resultado.paginas:
            if not _necesita_capa(r):
                continue
            pagina = pdf.pages[r.perfil.numero - 1]
            mb = [float(v) for v in pagina.mediabox]
            ancho, alto = mb[2] - mb[0], mb[3] - mb[1]
            rot = int(pagina.obj.get("/Rotate", 0)) % 360
            capa = pikepdf.open(io.BytesIO(_capa_pdf(r, ancho, alto, rot)))
            pagina.add_overlay(capa.pages[0])
        buf = io.BytesIO()
        pdf.save(buf)  # sin cifrado: el resultado es una copia de trabajo
    escribir_atomico(destino, buf.getvalue())


def _imagen_para_pdf(origen: Path, doc: Documento, indice: int) -> ImageReader:
    """Imagen a incrustar en el PDF, lo más liviana posible sin perder legibilidad.

    - JPEG de una página sin rotación EXIF: se incrusta tal cual (sin recomprimir).
    - Escaneo en blanco y negro puro: se mantiene sin pérdida (ocupa muy poco).
    - Resto: JPEG calidad 85.
    """
    if origen.suffix.lower() in (".jpg", ".jpeg") and len(doc) == 1:
        with Image.open(origen) as im:
            if im.getexif().get(0x0112, 1) == 1:
                return ImageReader(str(origen))
    arr, _ = doc.pagina(indice).imagen()
    img = Image.fromarray(arr)
    gris = img.convert("L")
    extremos = gris.histogram()
    if sum(extremos[1:255]) < 0.02 * gris.width * gris.height:  # casi solo blanco y negro
        return ImageReader(gris.point(lambda v: 255 if v > 127 else 0, mode="1"))
    buf = io.BytesIO()
    (gris if _es_gris(img) else img).save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)
    return ImageReader(buf)


def _es_gris(img: Image.Image) -> bool:
    import numpy as np

    a = np.asarray(img.resize((200, 200)), dtype=np.int16)
    return int(np.abs(a[:, :, 0] - a[:, :, 1]).max()) < 12 and int(np.abs(a[:, :, 1] - a[:, :, 2]).max()) < 12


def _desde_imagen(resultado: ResultadoDocumento, origen: Path, destino: Path) -> None:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    with Documento(origen) as doc:
        for r in resultado.paginas:
            ancho_pt, alto_pt = r.perfil.ancho_pt, r.perfil.alto_pt
            c.setPageSize((ancho_pt, alto_pt))
            c.drawImage(_imagen_para_pdf(origen, doc, r.perfil.numero - 1), 0, 0, width=ancho_pt, height=alto_pt)
            if _necesita_capa(r):
                _dibujar_capa_texto(c, r, ancho_pt, alto_pt)
            c.showPage()
    c.save()
    escribir_atomico(destino, buf.getvalue())
