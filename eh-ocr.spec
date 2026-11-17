# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: paquete portable en carpeta (onedir), sin consola, sin UPX.
#   pyinstaller eh-ocr.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RAIZ = Path(SPECPATH)
RECURSOS = RAIZ / "recursos"

datas = [(str(RECURSOS), "recursos")]
datas += collect_data_files("rapidocr")          # config, catálogo y modelos small de respaldo
datas += collect_data_files("spellchecker")      # diccionarios es/en/de
datas += collect_data_files("pdfplumber")
datas += collect_data_files("docx")              # plantilla de Word

hiddenimports = collect_submodules("rapidocr.inference_engine.onnxruntime")

a = Analysis(
    [str(RAIZ / "src" / "eh_ocr" / "__main__.py")],
    pathex=[str(RAIZ / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "torch", "paddle", "openvino", "tensorrt",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="eh-ocr",
    icon=str(RECURSOS / "eh-ocr.ico"),
    version=str(RAIZ / "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="eh-ocr")
