#!/usr/bin/env python3.13
"""Abre eh-ocr con Python.

- Doble clic: se abre sin ventana negra (.pyw usa pythonw).
- Desde PowerShell, en esta carpeta:  py -3.13 eh-ocr.pyw

Antes, una sola vez: instalar.py (instala las librerías, los modelos y Tesseract).
"""

import sys
from pathlib import Path

# Usa el código de esta misma carpeta, aunque eh-ocr no se haya instalado con pip.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _avisar(texto: str) -> None:
    """Aviso visible aunque no haya consola (doble clic) ni PySide6 instalado."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, texto, "eh-ocr", 0x10)
    else:
        print(texto, file=sys.stderr)


if __name__ == "__main__":
    if sys.version_info < (3, 13):
        _avisar(f"eh-ocr necesita Python 3.13 o superior (este es {sys.version.split()[0]}).\n"
                "Ábrelo con:  py -3.13 eh-ocr.pyw")
        sys.exit(1)
    try:
        for libreria in ("cv2", "PySide6", "pikepdf"):  # comprueba que estén instaladas
            __import__(libreria)
        from eh_ocr.__main__ import main
    except ImportError as e:
        _avisar(f"Faltan librerías de eh-ocr ({e.name}).\n\n"
                "Instálalas una vez con doble clic en instalar.py\n"
                "(o en PowerShell:  py -3.13 instalar.py).")
        sys.exit(1)
    sys.exit(main())
