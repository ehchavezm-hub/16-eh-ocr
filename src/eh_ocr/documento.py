"""Apertura de documentos (PDF e imágenes) y acceso página a página.

Las páginas se renderizan bajo demanda: un documento de miles de páginas
nunca se carga entero en memoria.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from . import config

EXT_PDF = {".pdf"}
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
EXT_ADMITIDAS = EXT_PDF | EXT_IMAGEN
EXT_HEIC = {".heic", ".heif"}

# PDFium no es seguro entre hilos: todo acceso pasa por este candado.
_PDFIUM = threading.RLock()
# Una imagen multipágina se recorre con seek(): también bajo candado.
_IMAGEN = threading.RLock()

# Si una imagen no indica su resolución, se asume que ocupa un ancho A4.
ANCHO_A4_PULGADAS = 8.27


class ErrorDocumento(Exception):
    """Error comprensible para el usuario."""


class ErrorContrasena(ErrorDocumento):
    def __init__(self, ruta: Path, incorrecta: bool = False):
        self.ruta = ruta
        self.incorrecta = incorrecta
        msg = "La contraseña no es correcta." if incorrecta else "El PDF está protegido con contraseña."
        super().__init__(msg)


class FormatoNoAdmitido(ErrorDocumento):
    pass


def es_admitido(ruta: Path) -> bool:
    return Path(ruta).suffix.lower() in EXT_ADMITIDAS


_RESULTADO = re.compile(r"_ocr( \(\d+\))?$", re.IGNORECASE)


def es_resultado_de_eh_ocr(ruta: Path) -> bool:
    """«contrato_ocr.pdf», «contrato_ocr (2).pdf»: salidas de eh-ocr, no se vuelven a procesar."""
    return bool(_RESULTADO.search(Path(ruta).stem))


def listar_archivos(rutas: list[Path]) -> list[Path]:
    """Expande carpetas (recursivo) y conserva el orden; incluye HEIC para avisar.

    Al expandir una carpeta se omiten los resultados de eh-ocr (…_ocr.pdf). Un archivo
    elegido directamente se respeta aunque lo parezca.
    """
    salida: list[Path] = []
    for ruta in rutas:
        ruta = Path(ruta)
        if ruta.is_dir():
            for hijo in sorted(ruta.rglob("*")):
                if (
                    hijo.is_file()
                    and hijo.suffix.lower() in EXT_ADMITIDAS | EXT_HEIC
                    and not es_resultado_de_eh_ocr(hijo)
                ):
                    salida.append(hijo)
        elif ruta.is_file():
            salida.append(ruta)
    return salida


@dataclass
class Pagina:
    documento: "Documento"
    indice: int  # 0-based

    @property
    def numero(self) -> int:
        return self.indice + 1

    def tamano_pt(self) -> tuple[float, float]:
        return self.documento._tamano_pt(self.indice)

    def imagen(self, dpi: int = config.DPI_RENDER) -> tuple[np.ndarray, float]:
        """Imagen RGB (alto, ancho, 3) y su resolución efectiva en DPI."""
        return self.documento._imagen(self.indice, dpi)

    def caracteres_digitales(self) -> int:
        return self.documento._caracteres(self.indice)

    def tiene_imagen_de_pagina_completa(self) -> bool:
        return self.documento._imagen_completa(self.indice)

    def es_foto(self) -> bool:
        return self.documento._es_foto


class Documento:
    """Envoltorio común para PDF e imágenes (TIFF multipágina incluido)."""

    def __init__(self, ruta: Path, contrasena: str | None = None):
        self.ruta = Path(ruta)
        ext = self.ruta.suffix.lower()
        self.contrasena = contrasena
        self._pdf: pdfium.PdfDocument | None = None
        self._img: Image.Image | None = None
        self._n_frames = 0
        self._dpi_original = None
        self._es_foto = False
        if ext in EXT_HEIC:
            raise FormatoNoAdmitido(
                "Formato HEIC no admitido. Guarda o comparte la foto como JPG desde el teléfono."
            )
        if ext in EXT_PDF:
            self.es_pdf = True
            try:
                self._pdf = pdfium.PdfDocument(str(self.ruta), password=contrasena)
            except pdfium.PdfiumError as e:
                if "password" in str(e).lower():
                    raise ErrorContrasena(self.ruta, incorrecta=contrasena is not None) from e
                raise ErrorDocumento(f"No se pudo abrir el PDF (archivo dañado o incompleto): {e}") from e
        elif ext in EXT_IMAGEN:
            self.es_pdf = False
            try:
                self._img = Image.open(self.ruta)
                exif = self._img.getexif()
                # Marca/modelo de cámara => foto de celular
                self._es_foto = bool(exif.get(0x010F) or exif.get(0x0110))
                self._n_frames = getattr(self._img, "n_frames", 1)
                self._dpi_original = self._img.info.get("dpi")
            except Exception as e:
                raise ErrorDocumento(f"No se pudo abrir la imagen (archivo dañado o formato raro): {e}") from e
        else:
            raise FormatoNoAdmitido(f"Formato {ext or 'sin extensión'} no admitido.")

    # --- API pública ---------------------------------------------------
    def __len__(self) -> int:
        return len(self._pdf) if self._pdf is not None else self._n_frames

    def paginas(self):
        for i in range(len(self)):
            yield Pagina(self, i)

    def pagina(self, indice: int) -> Pagina:
        return Pagina(self, indice)

    def cerrar(self) -> None:
        if self._pdf is not None:
            with _PDFIUM:
                self._pdf.close()
            self._pdf = None
        if self._img is not None:
            with _IMAGEN:
                self._img.close()
            self._img = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()

    # --- internos (todo acceso a PDFium bajo candado) --------------------
    def _dpi_imagen(self, ancho_px: int) -> float:
        dpi = self._dpi_original
        if dpi and dpi[0] and float(dpi[0]) > 30:
            return float(dpi[0])
        return ancho_px / ANCHO_A4_PULGADAS

    def _cuadro(self, i: int) -> Image.Image:
        """Página i de la imagen (lectura perezosa: solo esa página en memoria)."""
        with _IMAGEN:
            self._img.seek(i)
            cuadro = self._img.copy()
        return ImageOps.exif_transpose(cuadro) or cuadro

    def _tamano_pt(self, i: int) -> tuple[float, float]:
        if self._pdf is not None:
            with _PDFIUM:
                pagina = self._pdf[i]
                try:
                    w, h = pagina.get_size()
                finally:
                    pagina.close()
            return float(w), float(h)
        with _IMAGEN:
            self._img.seek(i)
            w, h = self._img.size
            orientacion = self._img.getexif().get(0x0112, 1)
        if orientacion in (5, 6, 7, 8):  # rotada 90°: ancho y alto se invierten
            w, h = h, w
        dpi = self._dpi_imagen(w)
        return w * 72 / dpi, h * 72 / dpi

    def _imagen(self, i: int, dpi: int) -> tuple[np.ndarray, float]:
        if self._pdf is not None:
            with _PDFIUM:
                pagina = self._pdf[i]
                try:
                    bmp = pagina.render(scale=dpi / 72)
                    img = bmp.to_pil().convert("RGB")
                    bmp.close()
                finally:
                    pagina.close()
            return np.asarray(img), float(dpi)
        cuadro = self._cuadro(i)
        return np.asarray(cuadro.convert("RGB")), self._dpi_imagen(cuadro.width)

    def _caracteres(self, i: int) -> int:
        if self._pdf is None:
            return 0
        with _PDFIUM:
            pagina = self._pdf[i]
            tp = pagina.get_textpage()
            try:
                texto = tp.get_text_range()
            finally:
                tp.close()
                pagina.close()
        return sum(1 for c in texto if c.isalnum())

    def _imagen_completa(self, i: int) -> bool:
        """¿La página es (casi) toda una imagen? => PDF escaneado, aunque tenga capa de texto."""
        if self._pdf is None:
            return True
        with _PDFIUM:
            pagina = self._pdf[i]
            try:
                w, h = pagina.get_size()
                area_pagina = max(w * h, 1)
                for obj in pagina.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE], max_depth=2):
                    x0, y0, x1, y1 = obj.get_pos()
                    if (x1 - x0) * (y1 - y0) >= 0.6 * area_pagina:
                        return True
            finally:
                pagina.close()
        return False
