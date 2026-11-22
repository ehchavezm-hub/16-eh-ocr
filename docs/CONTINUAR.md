# Cómo continuar el desarrollo de eh-ocr (desde otra cuenta o sesión)

Estado al 18/11/2026. Todo está en GitHub, en el repositorio privado
`ehchavezm-hub/16-eh-ocr`, rama **`claude/clever-babbage-km096c`** (aún no está en `main`).

## 1. Qué abrir primero

| Archivo | Qué es |
|---|---|
| `CLAUDE.md` | Reglas no negociables e inicio/fin de sesión (Claude lo lee solo) |
| `docs/ALCANCE.md` | Alcance v6: fuente de verdad |
| `docs/eh-ocr-alcance.html` | El alcance completo en una página, con el diagrama de decisión |
| `docs/CHANGELOG.md` | Qué cambió en 0.1.0 y 0.2.0 |
| `docs/respaldo/historial-conversacion.md` | Todos los mensajes de la conversación de desarrollo (decisiones, errores, pruebas) |
| `docs/respaldo/mockup/project/*.dc.html` | Copia del mockup aprobado (Inicio, Procesando, Revisión) |
| `docs/respaldo/pizarra/` | Copia de la pizarra «cómo decide el OCR» (44 elementos en JSON) |

Los enlaces `claude.ai/artifact/...` del mockup y de la pizarra pertenecen a la cuenta anterior:
desde otra cuenta no se abren. Por eso sus contenidos están copiados en `docs/respaldo/`.

## 2. Primer mensaje sugerido para la nueva sesión de Claude

> Continúa el desarrollo de eh-ocr. Trabaja en la rama `claude/clever-babbage-km096c` del repo
> ehchavezm-hub/16-eh-ocr. Lee CLAUDE.md, docs/ALCANCE.md, docs/CHANGELOG.md y docs/CONTINUAR.md antes de
> hacer nada. El historial completo está en docs/respaldo/historial-conversacion.md.

Si la nueva sesión crea otra rama, primero debe traer esta: `git fetch origin claude/clever-babbage-km096c`
y partir de ella (o integrarla a `main` con pull request, si el usuario lo aprueba).

## 3. Estado

- Versión 0.2.0. 54 pruebas pasan (1 omitida); la construcción de Windows en GitHub Actions pasa.
- En la laptop del usuario funciona instalado sobre Python con `instalar.py` (la empresa bloquea
  `.exe` sin firma). Procesó un contrato real y generó los 6 resultados, pero demoró.
- Tras una caída del controlador NVIDIA con DirectML existe `datos\solo_cpu`: hoy trabaja en CPU.

## 4. Pendiente, en orden

1. **Velocidad**: pedir al usuario los segundos por página (pantalla Informes) y optimizar:
   Tesseract solo en zonas dudosas, tablas solo donde haya indicios, volver a probar la gráfica
   (borrar `datos\solo_cpu`) con una sola sesión DirectML.
2. **Seguridad** (esperando aprobación del usuario), primero las 4 altas:
   caché sin cifrar (incluye PDF con contraseña), resultado sin contraseña de PDF protegido,
   JavaScript/adjuntos del PDF original en el PDF buscable, archivos trampa que agotan memoria.
   Luego: aislamiento del análisis, huellas de tessdata/choco/pip, DLL, telemetría de ONNX Runtime,
   temporales de Tesseract, firma/huella del `.exe`. (Fórmulas en Excel y HTML en nombres: ya corregidos.)
3. Integrar a `main` con pull request y publicar 0.2.0 en Releases (cuando el usuario lo apruebe).
4. Fases siguientes: campos de facturas, orden por bloques, complemento de manuscritos y
   fórmulas (TrOCR / LaTeX-OCR en ONNX), aprendizaje del enrutador, tablas de varias páginas.

## 5. Preferencias del usuario

- Explicaciones en castellano sencillo; comandos de PowerShell paso a paso, uno por bloque.
- Hacer las cosas completas y revisadas; respetar cuando pide «aún no desarrolles nada».
- No procesar archivos sin que pulse «Procesar seleccionados».
