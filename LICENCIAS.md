# Licencias de los componentes de eh-ocr

eh-ocr solo usa componentes gratuitos con licencias permisivas (MIT, BSD, Apache 2.0,
MPL 2.0) o LGPL enlazada dinámicamente y sin modificar. **No incluye nada AGPL, GPL ni
de uso no comercial.** La verificación es automática en cada construcción
(`scripts/verificar_licencias.py`).

## Motores y modelos

| Componente | Uso | Licencia |
|---|---|---|
| RapidOCR 3.x | Motor OCR principal | Apache 2.0 |
| Modelos PP-OCRv6 (PaddleOCR, formato ONNX) | Detección y reconocimiento de texto | Apache 2.0 |
| Tesseract 5 (binario incluido) | Segundo motor (votación) y orientación | Apache 2.0 |
| tessdata_best `spa`, `eng`, `deu` + `osd` | Modelos de Tesseract | Apache 2.0 |
| ONNX Runtime / ONNX Runtime DirectML | Ejecución de modelos y aceleración por gráfica | MIT |
| pyspellchecker (diccionarios es/en/de) | Corrector de confusiones típicas | MIT |

## Documentos y salidas

| Componente | Uso | Licencia |
|---|---|---|
| pypdfium2 (PDFium) | Abrir y renderizar PDF | Apache 2.0 / BSD-3 |
| pdfplumber + pdfminer.six | Texto digital de PDF | MIT |
| pikepdf (qpdf) | PDF con texto buscable | MPL 2.0 (qpdf: Apache 2.0) |
| reportlab | Capa de texto invisible del PDF | BSD |
| python-docx | Salida Word | MIT |
| openpyxl | Salida Excel | MIT |
| OpenCV (headless) | Preproceso de imágenes | Apache 2.0 |
| Pillow | Imágenes | MIT-CMU |
| NumPy | Cálculo | BSD-3 |

## Interfaz

| Componente | Uso | Licencia |
|---|---|---|
| PySide6 / Qt 6 (Essentials) | Interfaz gráfica | LGPL 3.0 (enlace dinámico; las DLL de Qt se distribuyen sin modificar en la carpeta del programa y pueden reemplazarse) |

## Binarios de Tesseract para Windows

Se copian de la instalación de Tesseract para Windows (compilación de UB Mannheim).
Sus DLL son de licencias permisivas (Leptonica BSD-2, libpng, libjpeg-turbo BSD/IJG,
libtiff, zlib, libwebp BSD, OpenJPEG BSD, giflib MIT, libarchive BSD, libcurl MIT) o
LGPL enlazadas dinámicamente (por ejemplo, componentes de GLib/Pango usados por las
herramientas de entrenamiento), y el runtime de GCC con su excepción de enlace.

## Excluidos a propósito

PyMuPDF (AGPL), marker (GPL), Surya (GPL), nougat (CC-BY-NC), OCRmyPDF (depende de
Ghostscript, AGPL), Kraken (fuera de alcance), HEIC (sus librerías pueden incluir GPL).
