"""Arranque de eh-ocr.exe (PyInstaller necesita un script sin importaciones relativas)."""

import sys

from eh_ocr.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
