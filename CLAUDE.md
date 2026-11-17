# eh-ocr — Instrucciones para Claude

## INICIO DE SESIÓN — hacer esto primero, siempre

```bash
cd /home/user/16-eh-ocr 2>/dev/null || git clone --depth 1 https://github.com/ehchavezm-hub/16-eh-ocr /home/user/16-eh-ocr && cd /home/user/16-eh-ocr
git pull origin main 2>/dev/null || true
pip install -e ".[dev]" -q 2>/dev/null || true
```

Para pruebas en Linux: `apt-get install -y tesseract-ocr tesseract-ocr-spa tesseract-ocr-deu libegl1 libgl1 libxkbcommon0`.

## FIN DE SESIÓN — hacer esto siempre al terminar

```bash
cd /home/user/16-eh-ocr
pytest -q
git add -A
git diff --cached --quiet || git commit -m "auto: cambios de sesión $(date +%Y-%m-%d\ %H:%M)"
git push origin main
```

## Proyecto

- **Nombre**: eh-ocr v0.1.0 — app independiente (no depende de txt2media)
- **Repo**: https://github.com/ehchavezm-hub/16-eh-ocr (privado)
- **Alcance**: ALCANCE.md (fuente de verdad) · Mockup aprobado: enlace en ALCANCE.md
- **Python**: 3.13 · **Interfaz**: PySide6 (Essentials)
- **Tests**: `pytest -v` · **Licencias**: `python scripts/verificar_licencias.py`

## Reglas técnicas (no negociables)

- 100 % gratuito; sin AGPL, GPL ni no comercial (LGPL solo enlace dinámico). Excluidos:
  PyMuPDF, marker, Surya, nougat, OCRmyPDF/Ghostscript, Kraken, HEIC.
- Absolutamente autónomo: `red.bloquear_red()` al iniciar; nada descarga ni conecta en ejecución.
  Los modelos se incluyen en la construcción (`scripts/preparar_build.py`).
- Motores en ONNX con ONNX Runtime + DirectML; sin PyTorch, PaddlePaddle ni OpenVINO.
- Escritura atómica (`archivos.escribir_atomico`) en todas las salidas; nunca sobrescribir
  (`archivos.ruta_unica`).
- Nunca entregar basura en silencio: toda palabra lleva confianza; lo dudoso se marca.
- Registros sin contenido de documentos. Datos propios en `eh-ocr\datos\`, nunca en el registro de Windows.
- Interfaz y mensajes en castellano claro, sin jerga.
- RapidOCR: `Global.use_cls` desactivado (invierte líneas); la orientación se corrige por página.
