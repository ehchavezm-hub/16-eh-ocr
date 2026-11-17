# PROMPT DE ALCANCE — eh-ocr (v6)

> Aplicativo independiente. No forma parte de txt2media ni depende de él.
> Estado: **alcance cerrado** — pendiente de aprobación para iniciar el desarrollo.

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
  32 GB de RAM, gráfica integrada Intel Arc, NPU Intel AI Boost, Windows 11 Pro 25H2 (64 bits),
  equipo corporativo unido a dominio.
- **Mínimo soportado:** Intel Core i5 de 11.ª generación, 8 GB de RAM, Windows 10/11 de 64 bits.
- **Aceleración automática:** un solo acelerador, **ONNX Runtime + DirectML** (MIT), que usa
  cualquier gráfica compatible con Windows (Intel Arc, Iris Xe, NVIDIA, AMD). Si no hay gráfica
  compatible o falla, vuelve a CPU sin intervención del usuario. No se usa la NPU (se descartó
  OpenVINO para ahorrar ~150–200 MB).
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
   Mide la confianza por palabra, por línea y por página. Si baja del umbral, la región se
   reintenta con otro preproceso, pasa a otro motor o se resuelve por votación.
5. SALIDA
   TXT, Markdown, JSON con estructura (bloques, coordenadas, confianza, motor usado),
   PDF con texto buscable (pikepdf o pypdfium2), DOCX (python-docx) y CSV/XLSX para tablas
   (openpyxl).

## Tabla de enrutamiento (motores gratuitos, locales, ONNX)
| Situación detectada | Motor principal | Si no alcanza… |
|---|---|---|
| PDF con texto digital | pdfplumber + pypdfium2 (sin OCR) | — |
| Estructura: columnas, títulos, orden de lectura | RapidLayout (ONNX) | Reglas geométricas de orden de lectura |
| Texto impreso escaneado | RapidOCR modelos *server* (ONNX) | Votación con Tesseract (tessdata_best) |
| Fotos de celular | Preproceso de perspectiva/iluminación + RapidOCR *server* | Reintento con otro preproceso + votación |
| Tablas | RapidTable (ONNX) | Reconstrucción por líneas/celdas + votación del texto de cada celda |
| Facturas, recibos, formularios | RapidLayout + RapidTable + reglas de extracción de campos | Votación |
| Escritura a mano *(complemento)* | TrOCR (ONNX, cuantizado) | Votación con RapidOCR; si persiste, marcar para revisión |
| Fórmulas matemáticas *(complemento)* | Modelo LaTeX-OCR en ONNX (p. ej. RapidLaTeXOCR, licencia a verificar) | Reintento con otro preproceso |
| Casos imposibles (mezcla, muy mala calidad) | Votación de todos los motores | Marcar para revisión, indicando las zonas no confiables |

> **Sin complemento:** las regiones detectadas como manuscrito o fórmula se marcan como
> "no procesadas — requiere el complemento" en la vista previa y en el informe. Nunca se entrega
> un resultado inventado.
>
> Antes de programar se verifica versión, licencia (código y pesos) y precisión real de cada
> motor. Si docling (con PyTorch) supera claramente a RapidLayout/RapidTable con el corpus del
> usuario, se reevalúa su inclusión.

## Inteligencia
- **Primero lo barato:** una página digital nunca pasa por OCR.
- **Votación por defecto** en toda página escaneada o fotografiada: dos motores en paralelo,
  alineación palabra a palabra; donde no coinciden, decide un tercero o el reintento con otro
  preproceso.
- **Confianza medida:** umbrales por motor y tipo de contenido, calibrados con el corpus.
- **Corrección final:** corrector ortográfico por idioma con diccionarios incluidos, y reglas
  para confusiones típicas (rn↔m, 0↔O, 1↔l). Cada cambio queda marcado.
- **Aprendizaje local:** registra qué motor rindió mejor por tipo de documento y ajusta el
  enrutador. Todo queda en el equipo.

## Comportamiento ante situaciones especiales
- **PDF con contraseña:** pide la clave. En lotes, deja el archivo pendiente, sigue con los
  demás y al final pide todas las claves juntas. La clave nunca se guarda.
- **Página que se cuelga** (archivo dañado o malicioso): tiempo límite automático por página;
  se marca "no procesada", se sigue con el resto y se puede reintentar.
- **Archivo de salida existente:** se renombra (`informe (1).txt`), nunca se sobrescribe.
- **Carpeta de salida:** junto al original; si no hay permiso de escritura, `Documentos\eh-ocr`.

## Interfaz (PySide6)
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

## Tamaño estimado
Estimación por componentes (a confirmar al construir los paquetes):

**Paquete esencial (`eh-ocr.zip`)**

| Componente | Descomprimido aprox. |
|---|---|
| Python 3.13 + librerías base | ~40 MB |
| PySide6 (solo módulos necesarios) | ~100 MB |
| numpy + OpenCV + Pillow | ~115 MB |
| Lectores/escritores PDF, DOCX, XLSX | ~45 MB |
| ONNX Runtime + DirectML | ~50 MB |
| RapidOCR modelos *server* | ~150–250 MB |
| Tesseract + castellano, inglés, alemán (best) | ~75 MB |
| RapidLayout + RapidTable | ~50–150 MB |
| Diccionarios ortográficos (3 idiomas) | ~15 MB |
| **Total descomprimido** | **~550–750 MB** |
| **ZIP a descargar** | **~400–550 MB** |

**Complemento manuscritos y fórmulas**

| Componente | Descomprimido aprox. |
|---|---|
| TrOCR manuscritos (ONNX cuantizado) | ~300–350 MB |
| Fórmulas LaTeX-OCR (ONNX) | ~100 MB |
| **Total descomprimido** | **~450 MB** |
| **ZIP a descargar** | **~350 MB** |

Sin PyTorch, PaddlePaddle ni OpenVINO se evitan ~1,4 GB adicionales.

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
