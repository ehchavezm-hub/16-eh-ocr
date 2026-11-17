# Cambios

## 0.1.0 — Fase 1 (núcleo)

- Análisis por página: texto digital, escaneo o foto (EXIF o iluminación despareja).
- PDF digital: texto exacto sin OCR (pdfplumber + pypdfium2).
- Preproceso: orientación 90/180/270 (Tesseract OSD), enderezado, perspectiva y sombras
  en fotos, ampliación a 300 DPI, ruido y contraste.
- Dos motores en paralelo (RapidOCR PP-OCRv6 + Tesseract) con votación palabra a palabra
  y reintentos con variantes de imagen si la confianza es baja.
- Corrector de confusiones típicas con diccionarios castellano, inglés y alemán.
- Salidas: PDF buscable, Word, TXT, Markdown, JSON. Escritura atómica, nunca sobrescribe.
- Interfaz PySide6 según el mockup: Procesar, Cola y lotes, Revisar, Informes.
- PDF con contraseña, tiempo límite por página, reanudación tras interrupción, red bloqueada.
- Paquete portable para Windows construido en GitHub Actions, con autoprueba del .exe.
