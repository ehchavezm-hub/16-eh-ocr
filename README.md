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

En equipos corporativos que bloquean `.exe` sin firma, ver «Equipos que bloquean el .exe».
Una vez instalado, se abre con el acceso directo **eh-ocr** (Escritorio) o **Abrir eh-ocr**
(carpeta del proyecto), o con `py -3.13 -m eh_ocr`.

Si eh-ocr se cerró de golpe alguna vez (por ejemplo, por el controlador de la tarjeta gráfica),
desde entonces usa el procesador y lo indica en «Estado del equipo». Para volver a probar la
gráfica, borra el archivo `datos\solo_cpu`. Los detalles de una caída quedan en `datos\caidas.log`.

Resultados: junto al original, como `nombre_ocr.pdf` (PDF con texto buscable) y
`nombre_ocr.docx` (Word). También Excel, TXT, Markdown y JSON. Nunca se sobrescribe nada.

Las **tablas** se detectan (con o sin bordes, también celdas combinadas) y salen como tablas
reales en Word y Excel.

## Equipos que bloquean el .exe (laptops corporativas)

Si Windows responde «Acceso denegado» al abrir `eh-ocr.exe` (política de control de
aplicaciones de la empresa), instala eh-ocr sobre Python, igual que txt2media:

```bash
git pull
```

```bash
py -3.13 instalar.py "D:\PST\x"
```

(«D:\PST\x» = carpeta descomprimida del ZIP, la que tiene `eh-ocr.exe` y `_internal`). Copia
los modelos y Tesseract del ZIP, prueba eh-ocr sin internet y crea el acceso directo **eh-ocr**
en el Escritorio. Funciona igual que el `.exe`.

## Cómo funciona por dentro

1. **Análisis de cada página**: ¿texto digital, escaneo o foto?
2. **Preproceso**: orientación, enderezado, perspectiva y sombras (fotos), resolución, ruido.
3. **RapidOCR PP-OCRv6** lee la página; si la confianza es baja, reintenta con otras versiones
   de la imagen.
4. **Tesseract** lee una vez la mejor versión, en el idioma detectado, y se **vota** palabra a
   palabra. Si una página tarda demasiado o un motor falla, se relee en modo rápido.
5. **Corrección** de confusiones típicas (rn↔m, 0↔O…) con diccionarios castellano, inglés y alemán.
6. **Salidas** y revisión: las palabras dudosas se corrigen con un clic.

Una página con texto digital nunca pasa por OCR: sale exacta e instantánea.

## Estado

- **0.1.0 — Fase 1 (núcleo)**: PDF digital, escaneos, fotos, votación, revisión, salidas, paquete portable.
- **0.2.0 — Tablas**: tablas con y sin bordes (alta precisión), celdas combinadas, salida Excel,
  lista con casillas, dos columnas, PDF más liviano. ZIP 531 MB.
- Próximas: complemento de manuscritos y fórmulas, aprendizaje del enrutador.

## Desarrollo

```bash
pip install -e ".[dev]"
pip install --no-deps -r requirements-tablas.txt
pytest -v
python -m pyflakes src tests scripts instalar.py
```

(Las librerías de tablas se instalan sin dependencias porque pedirían versiones de
ONNX Runtime y OpenCV que chocan con las que usa eh-ocr.)

Para probar con la misma precisión que el `.exe` (descarga una sola vez los modelos):

```bash
python scripts/preparar_build.py --solo-modelos
```

- Probar con tus documentos: ver `scripts/evaluar_corpus.py` (carpeta `corpus/`, nunca se sube).
- Construir el paquete de Windows: se hace automáticamente en GitHub Actions al crear un
  tag `v*` (o manualmente desde la pestaña Actions → eh-ocr → Run workflow).
