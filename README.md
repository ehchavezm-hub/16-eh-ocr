# eh-ocr

App de escritorio para Windows dedicada exclusivamente a OCR: **gratuita, autónoma (sin
internet) y portable**. Convierte PDF, escaneos y fotos en texto fiel, y marca en amarillo
lo que no es seguro en lugar de entregarlo como si estuviera bien.

Alcance completo: [ALCANCE.md](ALCANCE.md) · Licencias: [LICENCIAS.md](LICENCIAS.md)

## Usarla

1. Descarga `eh-ocr.zip` desde **Releases** de este repositorio.
2. Descomprímelo donde quieras (también en un USB). No necesita instalación ni administrador.
3. Abre `eh-ocr\eh-ocr.exe` y arrastra tus documentos.

La primera vez Windows puede mostrar "Windows protegió su PC": pulsa **Más información →
Ejecutar de todas formas**.

Resultados: junto al original, como `nombre_ocr.pdf` (PDF con texto buscable) y
`nombre_ocr.docx` (Word). También TXT, Markdown y JSON. Nunca se sobrescribe nada.

## Cómo funciona por dentro

1. **Análisis de cada página**: ¿texto digital, escaneo o foto?
2. **Preproceso**: orientación, enderezado, perspectiva y sombras (fotos), resolución, ruido.
3. **Dos motores en paralelo** (RapidOCR PP-OCRv6 + Tesseract) y **votación** palabra a palabra.
4. **Control de confianza**: si la página sale con baja confianza, se reintenta con otras
   versiones de la imagen.
5. **Corrección** de confusiones típicas (rn↔m, 0↔O…) con diccionarios castellano, inglés y alemán.
6. **Salidas** y revisión: las palabras dudosas se corrigen con un clic.

Una página con texto digital nunca pasa por OCR: sale exacta e instantánea.

## Estado

**Fase 1 (núcleo)** completa: PDF digital, escaneos, fotos, votación, revisión, todas las
salidas, paquete portable. Próximas fases: tablas y estructura (RapidLayout/RapidTable),
complemento de manuscritos y fórmulas, aprendizaje del enrutador.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest -v
```

- Probar con tus documentos: ver `scripts/evaluar_corpus.py` (carpeta `corpus/`, nunca se sube).
- Construir el paquete de Windows: se hace automáticamente en GitHub Actions al crear un
  tag `v*` (o manualmente desde la pestaña Actions → eh-ocr → Run workflow).
