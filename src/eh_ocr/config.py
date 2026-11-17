"""Rutas y parámetros globales de eh-ocr.

eh-ocr es portable: todo (modelos, Tesseract, datos) vive dentro de su
propia carpeta. Nunca se escribe en el registro de Windows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ES_WINDOWS = sys.platform == "win32"
ES_EMPAQUETADO = getattr(sys, "frozen", False)


def carpeta_base() -> Path:
    """Carpeta raíz de la instalación portable (donde está eh-ocr.exe)."""
    if ES_EMPAQUETADO:
        return Path(sys.executable).resolve().parent
    # En desarrollo: raíz del repositorio (src/eh_ocr/config.py -> ../../)
    return Path(__file__).resolve().parents[2]


def carpeta_recursos() -> Path:
    """Recursos incluidos: modelos, Tesseract, diccionarios."""
    if ES_EMPAQUETADO:
        # PyInstaller onedir deja los datos en _internal/ (sys._MEIPASS)
        return Path(getattr(sys, "_MEIPASS", carpeta_base())) / "recursos"
    return carpeta_base() / "recursos"


def carpeta_datos() -> Path:
    """Datos propios (aprendizaje, trabajos reanudables, preferencias)."""
    override = os.environ.get("EH_OCR_DATOS")
    ruta = Path(override) if override else carpeta_base() / "datos"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_complementos() -> Path:
    return carpeta_base() / "complementos"


def carpeta_modelos() -> Path:
    return carpeta_recursos() / "modelos"


def ruta_tesseract() -> Path | None:
    """Ejecutable de Tesseract incluido; en desarrollo, el del sistema."""
    nombre = "tesseract.exe" if ES_WINDOWS else "tesseract"
    incluido = carpeta_recursos() / "tesseract" / nombre
    if incluido.exists():
        return incluido
    from shutil import which

    encontrado = which("tesseract")
    return Path(encontrado) if encontrado else None


def carpeta_tessdata() -> Path | None:
    incluida = carpeta_recursos() / "tesseract" / "tessdata"
    return incluida if incluida.exists() else None


# --- Parámetros de calidad -------------------------------------------------

IDIOMAS = ("es", "en", "de")
IDIOMAS_TESSERACT = "spa+eng+deu"

DPI_RENDER = 300            # resolución de trabajo para páginas escaneadas
DPI_MINIMO = 300            # por debajo se amplía la imagen
UMBRAL_PALABRA = 0.80       # confianza mínima de una palabra para no marcarla dudosa
UMBRAL_PAGINA = 0.90        # confianza media mínima; por debajo se reintenta
MIN_CARACTERES_DIGITALES = 20  # una página con menos texto digital se trata como imagen

TIEMPO_LIMITE_BASE_S = 120  # tiempo límite por página (se ajusta al equipo)
