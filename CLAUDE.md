# eh-ocr — Instrucciones para Claude

## INICIO DE SESIÓN — hacer esto primero, siempre

```bash
cd /home/user/16-eh-ocr 2>/dev/null || git clone --depth 1 https://github.com/ehchavezm-hub/16-eh-ocr /home/user/16-eh-ocr && cd /home/user/16-eh-ocr
git pull origin main 2>/dev/null || true
pip install -e ".[dev]" -q 2>/dev/null || true
pip install --no-deps -r desarrollo/requirements-tablas.txt -q 2>/dev/null || true
```

Para pruebas en Linux: `apt-get install -y tesseract-ocr tesseract-ocr-spa tesseract-ocr-deu libegl1 libgl1 libxkbcommon0`.

## FIN DE SESIÓN — hacer esto siempre al terminar

```bash
cd /home/user/16-eh-ocr
pytest -q
python -m pyflakes src desarrollo instalar.py
git add -A
git diff --cached --quiet || git commit -m "auto: cambios de sesión $(date +%Y-%m-%d\ %H:%M)"
git push -u origin "$(git branch --show-current)"
```

Push directo a `main` no está permitido en las sesiones: se trabaja en la rama de la sesión
(`claude/...`) y se integra a `main` con pull request cuando el usuario lo aprueba.

## Proyecto

- **Nombre**: eh-ocr v0.2.0 — app independiente (no depende de txt2media)
- **Repo**: https://github.com/ehchavezm-hub/16-eh-ocr (privado)
- **Alcance**: docs/ALCANCE.md (fuente de verdad) · Mockup aprobado: enlace en docs/ALCANCE.md
- **Python**: 3.13 · **Interfaz**: PySide6 (Essentials)
- **Tests**: `pytest -v` · **Licencias**: `python desarrollo/scripts/verificar_licencias.py`

## Reglas técnicas (no negociables)

- 100 % gratuito; sin AGPL, GPL ni no comercial (LGPL solo enlace dinámico). Excluidos:
  PyMuPDF, marker, Surya, nougat, OCRmyPDF/Ghostscript, Kraken, HEIC.
- Absolutamente autónomo: `red.bloquear_red()` al iniciar; nada descarga ni conecta en ejecución.
  Los modelos se incluyen en la construcción (`desarrollo/scripts/preparar_build.py`).
- Motores en ONNX con ONNX Runtime + DirectML; sin PyTorch, PaddlePaddle ni OpenVINO.
- Escritura atómica (`archivos.escribir_atomico`) en todas las salidas; nunca sobrescribir
  (`archivos.ruta_unica`).
- Nunca entregar basura en silencio: toda palabra lleva confianza; lo dudoso se marca.
- Registros sin contenido de documentos. Datos propios en `eh-ocr\datos\`, nunca en el registro de Windows.
- Interfaz y mensajes en castellano claro, sin jerga.
- RapidOCR: `Global.use_cls` desactivado (invierte líneas); la orientación se corrige por página.
- rapid-table / rapid-layout: SIEMPRE `pip install --no-deps` (`desarrollo/requirements-tablas.txt`); con
  dependencias instalan opencv-python completo (+200 MB) y onnxruntime CPU (choca con DirectML).
- Tablas: las celdas guardan índices a las palabras de la página (no copias), para que las
  correcciones de la revisión lleguen a Word/Excel. Toda tabla pasa por `tablas.normalizar`
  (sin celdas superpuestas). Entre varios métodos gana el que no junta columnas.
- Excel: escribir siempre con `_poner` (un texto con «=» nunca es fórmula). Word/Excel: `texto_xml`.
- Documentos: nada se carga entero en memoria (PDF y TIFF página por página, PDFium bajo candado).
- Rendimiento: RapidOCR prueba versiones de la imagen; Tesseract corre UNA vez por página y solo
  en los idiomas presentes (`idiomas_presentes`). Tiempo límite 300 s → modo rápido (solo RapidOCR), nunca página perdida.
- DirectML: UNA instancia/sesión (una página a la vez en la gráfica); varias simultáneas tumbaron
  el controlador NVIDIA del usuario. Error de DirectML → CPU. Caída → `datos/caidas.log`; se crea
  `datos/solo_cpu` y desde entonces se usa CPU (borrarlo para volver a la gráfica).
- Lista: no se quitan archivos mientras se procesa (el avance usa los índices); `lista_cambiada`
  reinicia la revisión. La votación termina con `ordenar_por_columnas` (no reordenar solo por y).
- Dependencias con tope (versiones probadas); rapidocr fijado a 3.10.x (catálogo de modelos).
- Librerías rapid*: registran INFO al importarse → `config.silenciar_librerias()` tras cargarlas.
- Equipo del usuario: AppLocker bloquea `.exe` sin firma → se usa `instalar.py` (pythonw + acceso
  directo). Tesseract firmado sí corre.
- UI: todo texto de archivos/mensajes en HTML pasa por `html.escape`; tareas largas fuera del hilo
  de la ventana.
- UI SIEMPRE en tema claro (`estilo.CLARA`, `forzar_tema_claro`): decisión del usuario, aunque Windows
  esté en oscuro. Números con coma decimal (`estilo.num`/`pct`). Íconos dibujados con QPainter
  (`estilo.icono`), sin archivos ni complementos de imagen. Revisar ventanas en 980×640 (mínimo).
