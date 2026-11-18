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


_datos_cache: Path | None = None


def _escribible(ruta: Path) -> bool:
    try:
        ruta.mkdir(parents=True, exist_ok=True)
        prueba = ruta / ".eh-ocr-prueba"
        prueba.write_bytes(b"")
        prueba.unlink()
        return True
    except OSError:
        return False


def carpeta_datos() -> Path:
    """Datos propios (trabajos reanudables, registro).

    Normalmente `eh-ocr\\datos` (portable). Si esa carpeta no admite escritura (USB protegido,
    Archivos de programa), se usa la carpeta local del usuario. Nunca el registro de Windows.
    """
    global _datos_cache
    override = os.environ.get("EH_OCR_DATOS")
    if override:
        ruta = Path(override)
        ruta.mkdir(parents=True, exist_ok=True)
        return ruta
    if _datos_cache is not None:
        return _datos_cache
    candidatas = [carpeta_base() / "datos"]
    local = os.environ.get("LOCALAPPDATA")
    candidatas.append(Path(local) / "eh-ocr" / "datos" if local else Path.home() / ".eh-ocr" / "datos")
    for ruta in candidatas:
        if _escribible(ruta):
            _datos_cache = ruta
            return ruta
    raise OSError("eh-ocr no encontró una carpeta con permiso de escritura para sus datos.")


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
# Idioma detectado -> modelo de Tesseract (uno solo es varias veces más rápido que los tres)
TESSERACT_POR_IDIOMA = {"es": "spa", "en": "eng", "de": "deu"}

DPI_RENDER = 300            # resolución de trabajo para páginas escaneadas
DPI_MINIMO = 300            # por debajo se amplía la imagen
UMBRAL_PALABRA = 0.80       # confianza mínima de una palabra para no marcarla dudosa
UMBRAL_PAGINA = 0.90        # confianza media mínima; por debajo se reintenta
MIN_CARACTERES_DIGITALES = 20  # una página con menos texto digital se trata como imagen

TIEMPO_LIMITE_BASE_S = 300  # tiempo límite por página; si se supera, se relee en modo rápido
TIEMPO_LIMITE_RAPIDO_S = 120  # tiempo límite del modo rápido (solo RapidOCR)
