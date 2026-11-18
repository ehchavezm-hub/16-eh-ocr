# PROMPT DE ALCANCE — eh-ocr (v6)

> Aplicativo independiente. No forma parte de txt2media ni depende de él.
> Estado: **Fase 1 (núcleo) y tablas de la Fase 2 desarrolladas (v0.2.0)** — ver README.md y CHANGELOG.md.

## Rol
Actúa como arquitecto y desarrollador senior de sistemas de reconocimiento de documentos.
Vas a construir **eh-ocr**, una app de escritorio para Windows dedicada solo a OCR y extracción de
documentos. Debe ser la más precisa posible usando solo componentes gratuitos, combinados de forma
inteligente. Debe funcionar bien **en todos los casos**, no solo en documentos fáciles: el resultado
tiene que ser claramente superior al de las apps de OCR gratuitas disponibles.

## Identidad
- Nombre: **eh-ocr**
- Repositorio: https://github.com/ehchavezm-hub/16-eh-ocr (**privado**; todo el código,
  documentación, tests y releases van aquí)
- Licencia: ninguna pública (repositorio privado, todos los derechos reservados)
- Ejecutable: `eh-ocr.exe`
- Paquete Python: `eh_ocr`
- Versión inicial: 0.1.0
- Distribución: **paquete esencial + complemento opcional**
  - `eh-ocr.zip` (esencial): todo lo impreso — PDF digitales, escaneos, fotos, tablas, facturas
    y formularios — con máxima calidad, en los 3 idiomas.
  - `eh-ocr-complemento-manuscritos-formulas.zip`: manuscritos y fórmulas. Se descomprime en
    `eh-ocr\complementos\` y eh-ocr lo detecta solo al iniciar. Sin internet ni instalación.
- Actualizaciones: manuales, descargando el ZIP nuevo desde GitHub Releases
- Equipos que bloquean `.exe` sin firma (AppLocker/control de aplicaciones): instalación sobre
  Python con `instalar.py`, que toma modelos y Tesseract del ZIP y crea el acceso directo
  (mismo mecanismo que txt2media). Decisión del 18/11/2026.

## Objetivo
Convertir cualquier documento (PDF digital, PDF escaneado, imagen, foto de celular) en
texto fiel y estructurado. eh-ocr elige solo el motor más adecuado para cada página y
sube de nivel cuando la confianza es baja, sin intervención del usuario.

## Principios no negociables
1. **100 % gratuito.** Solo librerías y modelos gratuitos, con licencia MIT, BSD, Apache 2.0,
   MPL o LGPL (esta última solo con enlace dinámico, sin modificar). Nada de servicios de pago,
   nube, claves de API ni suscripciones. La potencia viene de combinar bien varios motores
   gratuitos.
2. **Funciona en todos los casos:** escaneos, PDF digitales, fotos de celular, tablas, facturas,
   manuscritos y fórmulas.
3. **Nunca entrega basura en silencio.** Cada palabra lleva su nivel de confianza; lo dudoso se
   marca en color en la vista previa y se reporta en el informe. Si algo no se pudo leer bien,
   eh-ocr lo dice claramente.
4. **Aplicación gráfica de Windows, no de consola.** Se abre con doble clic: sin ventana negra
   de DOS ni comandos, y sin archivos .bat para el usuario.
5. **Absolutamente autónoma.**
   - Funciona 100 % sin internet, siempre. No hace ninguna conexión de red: ni telemetría,
     ni descargas de modelos, ni comprobación de actualizaciones.
   - Todo viene incluido: modelos, binarios (Tesseract), diccionarios y runtimes
     (VC++, ONNX Runtime con DirectML). No requiere instalar nada más.
   - Portable: se descomprime y funciona. **Sin permisos de administrador** (apto para laptops
     corporativas administradas), sin modificar el registro, ejecutable desde un USB.
   - Cero configuración: detecta el idioma, el tipo de página, el hardware y el mejor motor.
     El usuario solo arrastra el archivo y recibe el resultado.
   - Se recupera sola: si un motor falla o se queda sin memoria, pasa al siguiente sin cerrarse.

## Equipo objetivo
- **Equipo de referencia (desarrollo y validación):** laptop Intel Core Ultra 7 255H,
  32 GB de RAM, gráfica integrada Intel Arc + gráfica NVIDIA (híbrida), NPU Intel AI Boost,
  Windows 11 Pro 25H2 (64 bits), equipo corporativo unido a dominio con control de aplicaciones
  (bloquea `.exe` sin firma: se instala con `instalar.py`).
- **Mínimo soportado:** Intel Core i5 de 11.ª generación, 8 GB de RAM, Windows 10/11 de 64 bits.
- **Aceleración automática:** un solo acelerador, **ONNX Runtime + DirectML** (MIT), que usa
  cualquier gráfica compatible con Windows (Intel Arc, Iris Xe, NVIDIA, AMD). Si no hay gráfica
  compatible o falla, vuelve a CPU sin intervención del usuario. No se usa la NPU (se descartó
  OpenVINO para ahorrar ~150–200 MB).
  - **Con la gráfica, una página a la vez** (una sola sesión DirectML): varias sesiones
    simultáneas hicieron caer el controlador NVIDIA. En CPU, varias páginas en paralelo.
  - Si la gráfica da un error, se continúa en CPU. Si una sesión termina de golpe, desde la
    siguiente eh-ocr usa solo el procesador en ese equipo y lo avisa (`datos\solo_cpu`; borrar
    ese archivo para volver a probar la gráfica). Las caídas quedan en `datos\caidas.log`.
- **Un solo modo de calidad: máxima.** No hay perfiles "ligeros"; el hardware solo define cuántas
  páginas se procesan en paralelo.

## Idiomas
- Incluidos de fábrica: **castellano, inglés y alemán**.
- Detección automática del idioma por página, incluso con varios idiomas en un mismo documento.
- Arquitectura de **paquetes de idioma** (`eh-ocr\idiomas\<código>\`: modelos OCR + diccionario
  ortográfico + reglas de corrección). Agregar un idioma = copiar una carpeta, sin tocar código.
- Interfaz en castellano.

## Fuera de alcance (eh-ocr NO hace)
- Texto a voz, video, generación de Office, traducción ni resumen.
- Edición de PDF, salvo incrustar la capa de texto buscable.
- Documentos históricos especializados (Kraken excluido).
- Formato HEIC: si llega uno, mensaje claro sugiriendo exportar a JPG.
- No depende de txt2media. Repo, instalador y versión propios.

## Reglas técnicas
- Python 3.13.
- Interfaz: **PySide6** (Qt, LGPL).
- Empaquetado: PyInstaller en modo carpeta (`--onedir`, `--noconsole`), **sin compresión UPX**,
  con nombre, versión y autor en las propiedades del .exe (reduce falsos positivos de antivirus).
  Se distribuye como ZIP: `eh-ocr\eh-ocr.exe`. Si el ZIP supera 2 GB (límite de GitHub), se
  divide en partes.
- **Motores en formato ONNX ejecutados con ONNX Runtime + DirectML, sin PyTorch, PaddlePaddle
  ni OpenVINO** en el paquete final. PyTorch solo se
  admite si un motor imprescindible no puede convertirse a ONNX, y debe justificarse.
- Licencias: PROHIBIDO cualquier componente AGPL, GPL o de uso no comercial, también como
  dependencia transitiva y en los pesos de modelos.
  - Excluidos: PyMuPDF, marker, Surya, nougat, OCRmyPDF (depende de Ghostscript, AGPL).
  - Mantener LICENCIAS.md con la licencia de cada dependencia y de cada modelo, y verificarla en CI.
- Escritura atómica (tempfile + os.replace) para todas las salidas.
- Procesamiento por página, en paralelo, cancelable y reanudable si se interrumpe.
  Documentos de cualquier tamaño (más de 500 páginas): se procesan por partes sin cargar todo
  en memoria.
- Datos propios (aprendizaje, preferencias, registros) dentro de la carpeta portable
  (`eh-ocr\datos\`), nunca en el registro de Windows. Los registros no guardan el contenido
  de los documentos.
- Test obligatorio: eh-ocr procesa documentos correctamente con la red deshabilitada y
  no intenta ninguna conexión.

## Pipeline
1. ANÁLISIS DE CADA PÁGINA (rápido, local, sin OCR)
   ¿Tiene texto digital? ¿Es foto o escaneo? Calidad, DPI, inclinación, ¿hay tablas,
   fórmulas, manuscrito? Idioma.
   Resultado: un perfil por página (JSON).
2. PREPROCESO (solo si la página es imagen)
   Enderezar, quitar ruido, ajustar contraste/binarizar, ampliar si el DPI es menor a 300 y
   corregir perspectiva, sombras e iluminación en fotos.
3. ENRUTADOR
   Elige el especialista según el perfil de la página. Una página puede usar varios
   especialistas a la vez, por ejemplo texto + tabla + fórmula en distintas regiones.
4. CONTROL DE CONFIANZA
   Mide la confianza por palabra, por línea y por página. Si baja del umbral, RapidOCR
   reintenta con otras versiones de la imagen; luego Tesseract lee UNA vez la mejor versión,
   solo en el idioma detectado, y se vota palabra a palabra.
5. SALIDA
   TXT, Markdown, JSON con estructura (bloques, coordenadas, confianza, motor usado),
   PDF con texto buscable (pikepdf o pypdfium2), DOCX (python-docx) y CSV/XLSX para tablas
   (openpyxl).

## Tabla de enrutamiento (motores gratuitos, locales, ONNX)
| Situación detectada | Motor principal | Si no alcanza… |
|---|---|---|
| PDF con texto digital | pdfplumber + pypdfium2 (sin OCR) | — |
| Estructura: columnas, títulos, orden de lectura | Orden geométrico (detección de dos columnas) | RapidLayout (pendiente: orden por bloques) |
| Texto impreso escaneado | RapidOCR PP-OCRv6 *medium* (ONNX) | Votación con Tesseract (tessdata_best, idioma detectado) |
| Fotos de celular | Preproceso de perspectiva/iluminación + RapidOCR *medium* | Reintento con otro preproceso + votación |
| Tablas | PDF digital: líneas del PDF (pdfplumber). Imagen: cuadrícula por bordes (OpenCV) | Zona por PP-DocLayout v3 + estructura por SLANet+, SLANet-en y alineación: gana la que no junta columnas |
| Facturas, recibos, formularios | RapidLayout + RapidTable + reglas de extracción de campos | Votación |
| Escritura a mano *(complemento)* | TrOCR (ONNX, cuantizado) | Votación con RapidOCR; si persiste, marcar para revisión |
| Fórmulas matemáticas *(complemento)* | Modelo LaTeX-OCR en ONNX (p. ej. RapidLaTeXOCR, licencia a verificar) | Reintento con otro preproceso |
| Casos imposibles (mezcla, muy mala calidad) | Votación de todos los motores | Marcar para revisión, indicando las zonas no confiables |

> **Sin complemento:** las regiones detectadas como manuscrito o fórmula se marcan como
> "no procesadas — requiere el complemento" en la vista previa y en el informe. Nunca se entrega
> un resultado inventado.
>
> Antes de programar se verifica versión, licencia (código y pesos) y precisión real de cada
> motor. Descartados para tablas: TableStructureRec (solo Python < 3.13, suma SciPy/scikit-image),
> UniTable y TableFormer/docling (requieren PyTorch). Si docling supera claramente a RapidLayout/RapidTable con el corpus del
> usuario, se reevalúa su inclusión.

## Inteligencia
- **Primero lo barato:** una página digital nunca pasa por OCR.
- **Votación por defecto** en toda página escaneada o fotografiada: RapidOCR y luego Tesseract
  (una vez, en el idioma detectado), alineación palabra a palabra; donde no coinciden deciden el
  diccionario y la confianza, y la palabra queda marcada con ambas lecturas.
- **Confianza medida:** umbrales por motor y tipo de contenido, calibrados con el corpus.
- **Corrección final:** corrector ortográfico por idioma con diccionarios incluidos, y reglas
  para confusiones típicas (rn↔m, 0↔O, 1↔l). Cada cambio queda marcado.
- **Aprendizaje local:** registra qué motor rindió mejor por tipo de documento y ajusta el
  enrutador. Todo queda en el equipo.

## Comportamiento ante situaciones especiales
- **PDF con contraseña:** pide la clave. En lotes, deja el archivo pendiente, sigue con los
  demás y al final pide todas las claves juntas. La clave nunca se guarda.
- **Página lenta o con error** (página muy densa, archivo dañado o malicioso): tiempo límite de
  300 s; si se supera o un motor falla, la página se relee en **modo rápido** (solo RapidOCR) y
  queda marcada. Solo si también falla queda "no procesada" y se puede reprocesar.
- **Avance visible:** total de páginas desde el inicio, páginas en lectura, porcentaje y tiempo
  restante estimado.
- **Archivo de salida existente:** se renombra (`informe (1).txt`), nunca se sobrescribe.
- **Carpeta de salida:** junto al original; si no hay permiso de escritura, `Documentos\eh-ocr`.

## Interfaz (PySide6)
- **Mockup aprobado:** https://claude.ai/artifact/TQooNLtLujGNeb8yBCX3A5 (privado) — 3 pantallas:
  Inicio, Procesando un lote y Revisión del resultado. Es la referencia visual de la interfaz.
- Lista con casillas: lo arrastrado o elegido se LISTA (sin repetidos y sin volver a tomar los
  resultados `…_ocr`); nada se procesa hasta pulsar «Procesar seleccionados».
- Ventana principal: arrastrar y soltar archivos o carpetas completas. Sirve igual para
  documentos sueltos y para lotes grandes.
- Vista previa lado a lado (imagen | texto) con zoom y las palabras de baja confianza
  resaltadas para corregirlas con un clic.
- Barra de progreso por documento y por página, con botón cancelar.
- Elegir formatos de salida.
- Informe por documento: motor por página, confianza media, páginas dudosas y tiempo.
- Modo claro/oscuro según Windows; compatible con pantallas de alta resolución.
- Castellano, con textos claros y sin jerga técnica.

## Calidad: metas y validación
- **Metas:** error de caracteres (CER) **< 1 %** en escaneos limpios y **< 5 %** en fotos.
- **Corpus de prueba:** documentos reales del usuario (20–30 variados como mínimo, de todos los
  tipos). El texto correcto se prepara de forma asistida: eh-ocr genera un borrador y el usuario
  lo corrige. Se guardan en una carpeta local excluida de git.
- **Prioridad de pruebas:** escaneos y PDFs primero; luego fotos, tablas, manuscritos y fórmulas.
- **Comparación obligatoria:** con el mismo corpus, eh-ocr debe superar a las apps de OCR
  gratuitas existentes. Si no las supera, no se entrega.
- Se miden CER, WER, precisión de tablas, tiempo por página y RAM máxima.

## Tamaño (medido en la construcción de Windows)

| Versión | ZIP a descargar | Descomprimido |
|---|---|---|
| 0.1.0 — núcleo (OCR medium + Tesseract) | 398 MB | 783 MB |
| 0.2.0 — + tablas de alta precisión y Excel | 531 MB | 930 MB |

Componentes principales: PySide6 (interfaz), OpenCV, ONNX Runtime DirectML, modelos PP-OCRv6
medium, Tesseract con castellano/inglés/alemán, PP-DocLayout v3, SLANet+ y SLANet-en.

**Complemento manuscritos y fórmulas (Fase 3, pendiente):** estimado ~450 MB descomprimido.

## Riesgos y requisitos externos
- **Laptop corporativa:** las políticas de TI pueden bloquear ejecutables no firmados aunque no
  requieran instalación. Antes de desarrollar, confirmar con el área de sistemas que se puede
  ejecutar un programa portable propio o solicitar su autorización (lista blanca).
- **SmartScreen:** la primera ejecución puede mostrar "Windows protegió su PC"
  → "Más información" → "Ejecutar de todas formas". Falsos positivos se reportan a Microsoft.
- **Manuscritos en castellano/alemán:** los modelos gratuitos están entrenados sobre todo en
  inglés; la precisión en cursiva desordenada será limitada y eh-ocr lo indicará.

## Fases y criterios de aceptación
1. **Núcleo:** análisis + pdfplumber/pypdfium2 + RapidOCR *server* + Tesseract + votación +
   interfaz + todas las salidas + aceleración DirectML. Criterio: escaneos y PDFs del corpus
   cumplen CER < 1 % sin internet en el equipo de referencia.
2. **Estructura y fotos:** RapidLayout, RapidTable, preproceso de fotos, facturas y formularios.
   ✅ Tablas (con y sin bordes, celdas combinadas, Word/Excel) y fotos en 0.2.0.
   Pendiente: extracción de campos de facturas/formularios y orden de lectura por bloques.
3. **Complemento:** manuscritos (TrOCR) y fórmulas (LaTeX-OCR) como paquete aparte, con
   detección automática en `eh-ocr\complementos\`.
4. **Inteligencia y pulido:** corrección final, aprendizaje del enrutador, `eh-ocr.zip` y el
   complemento en GitHub Releases, prueba en el equipo de referencia y en un equipo mínimo (i5 11.ª gen,
   8 GB), y comparación final contra apps existentes.

Cada fase incluye tests con pytest. CI en GitHub Actions (runner Windows): tests + verificación
de licencias + construcción del paquete (solo al publicar versiones).

## Antes de escribir código
- Verificar versiones actuales, licencias (código y pesos de modelos), compatibilidad con
  Python 3.13, ONNX Runtime + DirectML (gráfica Arc) y Windows de cada componente.
- Confirmar el tamaño real del paquete esencial y del complemento.
- Proponer la arquitectura de módulos (interfaz común `Motor` con `reconocer(pagina) → Resultado`)
  y esperar aprobación.
