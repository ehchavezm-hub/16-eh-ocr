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
datas += collect_data_files("rapid_layout")      # detector de zonas (incluye el modelo de tablas)
datas += collect_data_files("rapid_table")       # configuración de estructura de tablas
datas += collect_data_files("openpyxl")

hiddenimports = collect_submodules("rapidocr.inference_engine.onnxruntime")
_sin_torch = lambda nombre: "unitable" not in nombre and "torch" not in nombre  # noqa: E731
hiddenimports += collect_submodules("rapid_table", filter=_sin_torch)
hiddenimports += collect_submodules("rapid_layout", filter=_sin_torch)

a = Analysis(
    [str(RAIZ / "src" / "lanzador.py")],
    pathex=[str(RAIZ / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "pandas", "torch", "torchvision", "tokenizers", "paddle", "openvino", "tensorrt",
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
