# PROMPT DE ALCANCE — eh-ocr (v4)

> Aplicativo independiente. No forma parte de txt2media ni depende de él.
> Estado: **definición de alcance** — aún no se desarrolla código.

## Rol
Actúa como arquitecto y desarrollador senior de sistemas de reconocimiento de documentos.
Vas a construir **eh-ocr**, una app de escritorio para Windows dedicada solo a OCR y extracción de
documentos. Debe ser la más precisa posible usando solo componentes gratuitos, combinados de forma inteligente.

## Identidad
- Nombre: **eh-ocr**
- Repositorio: https://github.com/ehchavezm-hub/16-eh-ocr (todo el código, documentación,
  tests y releases van aquí)
- Ejecutable: `eh-ocr.exe`
- Paquete Python: `eh_ocr`
- Versión inicial: 0.1.0
- Distribución: **un solo paquete completo** (todos los motores, modelos e idiomas incluidos)

## Objetivo
Convertir cualquier documento (PDF digital, PDF escaneado, imagen, foto de celular) en
texto fiel y estructurado. eh-ocr elige solo el motor más adecuado para cada página y
sube de nivel cuando la confianza es baja, sin intervención del usuario.

## Principios no negociables
1. **100 % gratuito y de código abierto.** Solo librerías y modelos gratuitos, con licencia
   MIT, BSD, Apache 2.0, MPL o LGPL (esta última solo con enlace dinámico, sin modificar).
   Nada de servicios de pago, nube, claves de API ni suscripciones.
   La potencia no viene de un motor caro, sino de combinar bien varios motores gratuitos.
2. **Funciona en cualquier PC con Windows.** Windows 10 y 11 de 64 bits (el mínimo que admite
   Python 3.13). Sin necesidad de GPU, con 4 GB de RAM como mínimo, en CPUs antiguas o modestas.
   Si encuentra una GPU, la aprovecha automáticamente; si no, funciona igual.
3. **Aplicación gráfica de Windows, no de consola.** Se abre con doble clic como cualquier
   programa: sin ventana negra de DOS ni comandos, y sin archivos .bat para el usuario.
4. **Absolutamente autónoma.**
   - Funciona 100 % sin internet, siempre. No hace ninguna conexión de red: ni telemetría,
     ni descargas de modelos, ni comprobación de actualizaciones.
   - Todo viene incluido: modelos, binarios (Tesseract, etc.), diccionarios y runtimes
     (VC++, ONNX Runtime). No requiere instalar nada más.
   - Portable: se descomprime y funciona. No necesita permisos de administrador ni modificar
     el registro, y se puede ejecutar desde un USB.
   - Cero configuración: detecta el idioma, el tipo de página, el hardware y el mejor motor.
     El usuario solo arrastra el archivo y recibe el resultado.
   - Se recupera sola: si un motor falla o se queda sin memoria, pasa al siguiente sin cerrarse.

## Idiomas
- De fábrica: **español** e **inglés** [+ los sugeridos que se aprueben].
- Detección automática del idioma por página, incluso con varios idiomas en un mismo documento.
- Arquitectura de **paquetes de idioma** (`eh-ocr\idiomas\<código>\`: modelos OCR + diccionario
  ortográfico + reglas de corrección). Agregar un idioma = copiar una carpeta, sin tocar código.
- Interfaz en español.

## Fuera de alcance (eh-ocr NO hace)
- Texto a voz, video, generación de Office, traducción ni resumen.
- Edición de PDF, salvo incrustar la capa de texto buscable.
- No depende de txt2media. Repo, instalador y versión propios.

## Reglas técnicas
- Python 3.13.
- Interfaz: **PySide6** (Qt, LGPL).
- Empaquetado: PyInstaller en modo carpeta (`--onedir`, `--noconsole`). Así cumple con LGPL
  y arranca más rápido. Se distribuye como ZIP: `eh-ocr\eh-ocr.exe`.
- Licencias: PROHIBIDO cualquier componente AGPL, GPL o de uso no comercial, también como
  dependencia transitiva y en los pesos de modelos.
  - Excluidos: PyMuPDF, marker, Surya, nougat, OCRmyPDF (depende de Ghostscript, AGPL).
  - Mantener LICENCIAS.md con la licencia de cada dependencia y de cada modelo, y verificarla en CI.
- Preferir ONNX Runtime (CPU) frente a PyTorch o PaddlePaddle: es más liviano, más rápido en
  CPU y funciona en más equipos. Convertir modelos a ONNX cuando sea posible.
- Escritura atómica (tempfile + os.replace) para todas las salidas.
- Procesamiento por página, en paralelo según los núcleos y la RAM disponibles, cancelable y
  reanudable si se interrumpe.
- Datos propios (aprendizaje, preferencias, registros) dentro de la carpeta portable
  (`eh-ocr\datos\`), nunca en el registro de Windows. Los registros no guardan el contenido
  de los documentos.
- Test obligatorio: eh-ocr procesa documentos correctamente con la red deshabilitada y
  no intenta ninguna conexión.

## Autoajuste al equipo
Al iniciar, eh-ocr detecta CPU, núcleos, RAM, GPU y espacio en disco, y elige un perfil:
- **Ligero:** PC antigua o poca RAM. Tesseract y RapidOCR, una página a la vez.
- **Normal:** RapidOCR + docling, en paralelo.
- **Potente:** todos los especialistas, votación activa, GPU si existe.
Todos los motores vienen en el paquete; el perfil solo decide cuáles se usan y cuántos a la vez.
Los modelos pesados se cargan solo cuando una página los necesita y se liberan después.

## Pipeline
1. ANÁLISIS DE CADA PÁGINA (rápido, local, sin OCR)
   ¿Tiene texto digital? ¿Es foto o escaneo? Calidad, DPI, inclinación, ¿hay tablas,
   fórmulas, manuscrito? Idioma.
   Resultado: un perfil por página (JSON).
2. PREPROCESO (solo si la página es imagen)
   Enderezar, quitar ruido, ajustar contraste/binarizar, ampliar si el DPI es menor a 300 y
   corregir perspectiva en fotos.
3. ENRUTADOR
   Elige el especialista según el perfil de la página. Una página puede usar varios
   especialistas a la vez, por ejemplo texto + tabla + fórmula en distintas regiones.
4. CONTROL DE CONFIANZA
   Mide la confianza por palabra, por línea y por página. Si baja del umbral, la región pasa al
   siguiente motor local, se reintenta con otro preproceso o se activa la votación.
5. SALIDA
   TXT, Markdown, JSON con estructura (bloques, coordenadas, confianza, motor usado),
   PDF con texto buscable (pikepdf o pypdfium2), DOCX (python-docx) y CSV/XLSX para tablas
   (openpyxl).

## Tabla de enrutamiento (solo motores gratuitos y locales)
| Situación detectada | Motor principal | Si no alcanza, sube a… |
|---|---|---|
| PDF con texto digital | pdfplumber + pypdfium2 (sin OCR) | — |
| Estructura: columnas, títulos, orden de lectura | docling | — |
| Texto impreso escaneado | RapidOCR (ONNX) | PaddleOCR (perfil potente) + votación con Tesseract |
| Escaneo simple o PC sin recursos | Tesseract | RapidOCR |
| Tablas | docling | PP-Structure (perfil potente) |
| Escritura a mano | TrOCR (ONNX) | Votación TrOCR + Kraken; si persiste, marcar para revisión |
| Fórmulas matemáticas | pix2tex (salida LaTeX) | Preproceso alternativo + reintento |
| Facturas, recibos, formularios | docling (estructura) + reglas de extracción de campos | Votación de motores |
| Documentos históricos | Kraken | — |
| Casos imposibles (mezcla, muy mala calidad) | Votación de todos los motores disponibles | Modelo de visión local gratuito (solo en perfil potente, si su licencia lo permite) o marcar para revisión |

## Inteligencia (sin costo)
- **Primero lo barato:** una página digital nunca pasa por OCR.
- **Confianza medida:** umbrales por motor y tipo de contenido, ajustados automáticamente.
- **Múltiples intentos:** si la confianza es baja, reintenta con otro preproceso
  (otro contraste, binarización o escala) antes de cambiar de motor.
- **Votación:** dos motores en paralelo, alineación palabra a palabra; donde no coinciden, decide un
  tercero. Se activa sola en páginas difíciles o si el usuario elige precisión máxima.
- **Dos modos de velocidad** (opcional, por defecto Automático):
  - ⚡ Rápido: el primer motor que supere el umbral.
  - 🎯 Precisión máxima: votación en todas las páginas.
- **Corrección final:** corrector ortográfico por idioma con diccionarios incluidos, y reglas
  para confusiones típicas (rn↔m, 0↔O, 1↔l). Cada cambio queda marcado.
- **Aprendizaje local:** registra qué motor rindió mejor por tipo de documento y ajusta el
  enrutador. Todo queda en el equipo.

## Interfaz (PySide6)
- Ventana principal: arrastrar y soltar archivos o carpetas completas (lotes).
- Vista previa lado a lado (imagen | texto) con zoom y las palabras de baja confianza
  resaltadas para corregirlas con un clic.
- Barra de progreso por documento y por página, con botón cancelar.
- Elegir formatos de salida y carpeta destino (por defecto, junto al original).
- Informe por documento: motor por página, confianza media y tiempo.
- Modo claro/oscuro según Windows; compatible con pantallas de alta resolución.
- Español, con textos claros y sin jerga técnica.

## Fases y criterios de aceptación
1. **Núcleo:** análisis + pdfplumber/pypdfium2 + RapidOCR + Tesseract + docling + interfaz +
   todas las salidas + autoajuste al equipo. Criterio: funciona en una PC sin GPU, con 4 GB de RAM
   y sin internet; un PDF digital sale exacto sin usar OCR.
2. **Especialistas:** PaddleOCR/PP-Structure, TrOCR, pix2tex y Kraken (carga bajo demanda).
3. **Inteligencia:** reintentos, votación, corrección final y aprendizaje del enrutador.
4. **Pulido:** paquete completo `eh-ocr.zip` publicado como Release en GitHub. Pruebas en
   Windows 10 y 11 limpios (sin Python ni nada instalado) y en una PC modesta.

Cada fase incluye tests con pytest y un corpus de prueba con el resultado correcto
(*ground truth*). Se miden CER, WER, la precisión de las tablas, el tiempo por página y la RAM máxima.
CI en GitHub Actions (runner Windows): tests + verificación de licencias + construcción del paquete.

## Antes de escribir código
- Verificar las versiones actuales, las licencias (código y pesos de modelos) y la compatibilidad
  con Python 3.13, ONNX y Windows de cada librería.
- Estimar el tamaño final del paquete completo.
- Proponer la arquitectura de módulos (interfaz común `Motor` con `reconocer(pagina) → Resultado`)
  y esperar mi aprobación.

---

## PENDIENTES (cerrar antes de desarrollar)

### Riesgos técnicos a verificar
1. docling, pix2tex y TrOCR funcionan con PyTorch (más de 1 GB). ¿Se acepta PyTorch CPU en el
   paquete o se convierte todo a ONNX?
2. docling descarga sus modelos de internet la primera vez: hay que incluirlos en el paquete y
   desactivar la descarga.
3. Kraken tiene soporte oficial limitado en Windows.
4. Abrir fotos HEIC de iPhone puede requerir componentes GPL: verificar o quitar HEIC.
5. Tamaño del paquete completo: posiblemente 1,5–2 GB. ¿Aceptable?

### Decisiones
6. Idiomas finales. Sugeridos: portugués ⭐, francés, italiano, alemán, quechua, latín.
7. Licencia del propio eh-ocr (MIT, Apache 2.0, propietaria o repo privado).
8. Firma digital del .exe (SignPath gratuito para código abierto) o aceptar el aviso de SmartScreen.
9. Actualizaciones: descarga manual del ZIP desde GitHub Releases.
10. Metas de precisión numéricas (p. ej. CER < 1 % en escaneo limpio, < 5 % en fotos).
11. Origen del corpus de prueba (documentos reales o conjuntos públicos).

### Detalles por confirmar para el prompt
12. PDFs con contraseña: pedir la clave en lugar de fallar.
13. Archivos corruptos o maliciosos: tiempo límite por página.
14. Documentos enormes (más de 500 páginas): procesar por partes sin cargar todo en memoria.
15. Archivo de salida existente: ¿sobrescribir, renombrar o preguntar?
