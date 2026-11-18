"""Escritura segura de archivos.

- Escritura atómica (tempfile + os.replace): nunca queda un archivo a medias.
- Nunca se sobrescribe: si el destino existe se usa "nombre (1).ext".
- Salida junto al original; si no hay permiso, Documentos\\eh-ocr.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")


def texto_xml(texto: str) -> str:
    """Quita caracteres de control que Word y Excel no aceptan (vienen en algunos PDF)."""
    return _CONTROL.sub("", texto)


def escribir_atomico(destino: Path, contenido: bytes | str, codificacion: str = "utf-8") -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = contenido.encode(codificacion) if isinstance(contenido, str) else contenido
    fd, tmp = tempfile.mkstemp(prefix=".eh-ocr-", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return destino


def ruta_temporal_junto_a(destino: Path) -> Path:
    """Ruta temporal en la misma carpeta, para librerías que escriben a un path."""
    fd, tmp = tempfile.mkstemp(prefix=".eh-ocr-", suffix=destino.suffix, dir=destino.parent)
    os.close(fd)
    return Path(tmp)


def confirmar_temporal(tmp: Path, destino: Path) -> Path:
    os.replace(tmp, destino)
    return destino


def ruta_unica(carpeta: Path, nombre_base: str, extension: str) -> Path:
    """informe.txt, informe (1).txt, informe (2).txt…"""
    extension = extension if extension.startswith(".") else "." + extension
    candidato = carpeta / f"{nombre_base}{extension}"
    n = 1
    while candidato.exists():
        candidato = carpeta / f"{nombre_base} ({n}){extension}"
        n += 1
    return candidato


def carpeta_documentos() -> Path:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (Documentos)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def puede_escribir(carpeta: Path) -> bool:
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".eh-ocr-prueba-", dir=carpeta)
        os.close(fd)
        os.unlink(tmp)
        return True
    except OSError:
        return False


def carpeta_salida(origen: Path, preferida: Path | None = None) -> Path:
    """Junto al original; si no se puede escribir, Documentos\\eh-ocr."""
    for candidata in (preferida, Path(origen).parent):
        if candidata is not None and puede_escribir(candidata):
            return candidata
    respaldo = carpeta_documentos() / "eh-ocr"
    respaldo.mkdir(parents=True, exist_ok=True)
    return respaldo
