# Cambios

## 0.2.0 — Tablas y Excel

- Detección de tablas por capas:
  - PDF digital: tablas del propio PDF (pdfplumber), exactas.
  - Escaneos y fotos con bordes: cuadrícula por líneas (OpenCV), con celdas combinadas.
  - Tablas sin bordes: zona detectada por RapidLayout y estructura por RapidTable (SLANet+);
    respaldo por alineación del texto.
- Celdas de varios renglones unidas en su celda, en orden de lectura.
- Word: tablas reales con celdas combinadas. Excel (nuevo): una hoja por página, tablas con
  bordes y celdas combinadas, números como números. Markdown y TXT con tablas.
- Las correcciones hechas en la revisión aparecen también dentro de las tablas.
- Revisión: las tablas se marcan con un recuadro azul; el informe muestra cuántas hay.
- Tablas de alta precisión: detector de zonas PP-DocLayout v3 y dos modelos de estructura
  (SLANet+ y SLANet en inglés). Cada tabla se arma con todos los métodos disponibles y se elige
  la que no junta columnas.
- PDF digital: también se detectan tablas SIN líneas (antes solo las que tenían líneas).
- Lista con casillas: nada se procesa hasta pulsar «Procesar seleccionados»; sin duplicados.
- «Abrir carpeta de resultados» corregido en Windows.
- Excel: corregido «'value' is read-only» (celdas superpuestas). Si un formato falla, los
  demás se guardan igual.

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
