"""Pipeline completo de eh-ocr.

Por cada página:
  1. Análisis (¿texto digital? ¿escaneo? ¿foto?)
  2. Preproceso (orientación, inclinación, perspectiva, iluminación, resolución)
  3. Reconocimiento con dos motores en paralelo + votación
  4. Control de confianza: si es baja, reintenta con otras variantes de imagen
  5. Corrección de confusiones típicas y marcado de palabras dudosas

Los resultados de cada página se guardan en disco al terminarla: si el
proceso se interrumpe, se retoma donde quedó.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, hardware, preproceso, tablas
from .archivos import escribir_atomico
from .corrector import corregir_palabra, diccionarios
from .documento import Documento, Pagina
from .modelo import (
    EstadoPagina,
    Linea,
    PerfilPagina,
    ResultadoDocumento,
    ResultadoPagina,
    TipoPagina,
)
from .motores.pdf_digital import LectorPdfDigital
from .motores.rapid import MotorRapid
from .motores.tesseract import MotorTesseract
from .votacion import agrupar_en_lineas, marcar_dudosas, votar

log = logging.getLogger(__name__)

VERSION_CACHE = 2  # 2: tablas


class Cancelado(Exception):
    pass


@dataclass
class Progreso:
    archivo: Path
    pagina: int
    total: int
    detalle: dict = field(default_factory=dict)


@dataclass
class Control:
    """Pausa y cancelación desde la interfaz."""

    cancelar: threading.Event = field(default_factory=threading.Event)
    reanudar: threading.Event = field(default_factory=lambda: _evento_activo())

    def esperar_si_pausado(self) -> None:
        while not self.reanudar.wait(0.2):
            if self.cancelar.is_set():
                raise Cancelado()
        if self.cancelar.is_set():
            raise Cancelado()


def _evento_activo() -> threading.Event:
    e = threading.Event()
    e.set()
    return e


class Motores:
    """Instancias compartidas (los modelos se cargan una sola vez)."""

    _instancia: "Motores | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.rapid = MotorRapid()
        self.tesseract = MotorTesseract()

    @classmethod
    def obtener(cls) -> "Motores":
        with cls._lock:
            if cls._instancia is None:
                cls._instancia = Motores()
            return cls._instancia

    def estado(self) -> dict:
        return {
            "rapidocr": self.rapid.disponible(),
            "tesseract": self.tesseract.disponible(),
            "acelerador": self.rapid.acelerador,
            "modelos": self.rapid.modelos,
        }


# --- Caché reanudable --------------------------------------------------------

def firma_motores() -> str:
    """Qué motores y modelos hay disponibles. Si cambia (p. ej. se instala Tesseract o los
    modelos precisos), los documentos se vuelven a leer en vez de reutilizar resultados viejos."""
    m = Motores.obtener()
    et = tablas.ModelosTablas.obtener().estado
    return (
        f"rapid={m.rapid.disponible() and m.rapid.modelos}|tess={m.tesseract.disponible()}"
        f"|lay={et['layout_preciso']}|est={et['estructuras']}"
    )


def id_trabajo(ruta: Path) -> str:
    st = Path(ruta).stat()
    clave = f"{Path(ruta).resolve()}|{st.st_size}|{st.st_mtime_ns}|v{VERSION_CACHE}|{firma_motores()}"
    return hashlib.sha1(clave.encode("utf-8")).hexdigest()[:16]


def carpeta_trabajo(ruta: Path) -> Path:
    d = config.carpeta_datos() / "trabajos" / id_trabajo(ruta)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ruta_cache(ruta: Path, numero: int) -> Path:
    return carpeta_trabajo(ruta) / f"p{numero:05d}.json"


def cargar_cache(ruta: Path, numero: int) -> ResultadoPagina | None:
    p = _ruta_cache(ruta, numero)
    if not p.exists():
        return None
    try:
        return ResultadoPagina.de_dict(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return None


def guardar_cache(ruta: Path, r: ResultadoPagina) -> None:
    escribir_atomico(_ruta_cache(ruta, r.perfil.numero), json.dumps(r.a_dict(), ensure_ascii=False))


def limpiar_cache(dias: int = 30) -> int:
    """Borra los trabajos reanudables sin uso hace más de `dias` días. Devuelve cuántos."""
    import shutil

    base = config.carpeta_datos() / "trabajos"
    if not base.exists():
        return 0
    limite = time.time() - dias * 86400
    borrados = 0
    for d in base.iterdir():
        try:
            if d.is_dir() and max((f.stat().st_mtime for f in d.iterdir()), default=d.stat().st_mtime) < limite:
                shutil.rmtree(d)
                borrados += 1
        except OSError:
            continue
    return borrados


def borrar_cache_pagina(ruta: Path, numero: int) -> None:
    p = _ruta_cache(ruta, numero)
    if p.exists():
        p.unlink()


# --- Análisis ---------------------------------------------------------------

def perfilar(pagina: Pagina) -> PerfilPagina:
    ancho_pt, alto_pt = pagina.tamano_pt()
    chars = pagina.caracteres_digitales()
    if chars >= config.MIN_CARACTERES_DIGITALES and not pagina.tiene_imagen_de_pagina_completa():
        tipo = TipoPagina.DIGITAL
    elif pagina.es_foto():
        tipo = TipoPagina.FOTO
    else:
        tipo = TipoPagina.ESCANEO
    dpi = config.DPI_RENDER
    return PerfilPagina(
        numero=pagina.numero,
        tipo=tipo,
        ancho_px=int(round(ancho_pt * dpi / 72)),
        alto_px=int(round(alto_pt * dpi / 72)),
        dpi=float(dpi),
        ancho_pt=ancho_pt,
        alto_pt=alto_pt,
        caracteres_digitales=chars,
    )


def texto_digital_legible(palabras: list) -> bool:
    """¿El texto digital del PDF es legible? Detecta fuentes mal codificadas.

    Señales de basura: marcas «(cid:NN)», caracteres de reemplazo «�», o casi ninguna
    palabra reconocible en castellano, inglés o alemán.
    """
    if not palabras:
        return True
    textos = [p.texto for p in palabras]
    total = len(textos)
    raras = sum(1 for t in textos if "(cid:" in t or "\ufffd" in t)
    if raras / total > 0.05:
        return False
    largas = [t for t in textos if sum(c.isalpha() for c in t) >= 3]
    if len(largas) < 30:
        return True  # muy poco texto para juzgar
    dic = diccionarios()
    conocidas = sum(1 for t in largas if dic.conoce(t))
    return conocidas / len(largas) >= 0.2


def preparar_imagen(pagina: Pagina, perfil: PerfilPagina, motores: Motores) -> preproceso.ImagenTrabajo:
    imagen, dpi = pagina.imagen(config.DPI_RENDER)
    perfil.ancho_px, perfil.alto_px = imagen.shape[1], imagen.shape[0]
    perfil.dpi = dpi
    perfil.contraste = round(preproceso.contraste(imagen), 3)
    t = preproceso.ImagenTrabajo(imagen=imagen)

    # Una foto sin resolución declarada se trata como foto aunque no tenga EXIF
    if perfil.tipo == TipoPagina.FOTO:
        preproceso.corregir_perspectiva(t)
        preproceso.normalizar_iluminacion(t)
    elif not pagina.documento.es_pdf and preproceso.iluminacion_despareja(imagen) > 12:
        # Sombras o luz despareja: se trata como foto aunque no tenga datos de cámara
        perfil.tipo = TipoPagina.FOTO
        preproceso.corregir_perspectiva(t)
        preproceso.normalizar_iluminacion(t)
    elif preproceso.iluminacion_despareja(imagen) > 12:
        preproceso.normalizar_iluminacion(t)

    preproceso.ampliar_si_baja_resolucion(t, dpi if perfil.tipo != TipoPagina.FOTO else config.DPI_MINIMO)

    # Orientación 90/180/270 (detector de Tesseract)
    if motores.tesseract.disponible():
        grados, conf = motores.tesseract.orientacion(t.imagen)
        if grados and conf >= 2.0:
            preproceso.rotar_90(t, grados)
    perfil.rotacion = t.rotacion

    angulo = preproceso.estimar_inclinacion(t.imagen)
    preproceso.enderezar(t, angulo)
    perfil.inclinacion = t.inclinacion

    preproceso.quitar_ruido(t)
    if perfil.contraste < 0.5:
        preproceso.mejorar_contraste(t)
    return t


def _confianza_media(lineas: list[Linea]) -> float:
    pals = [p for l in lineas for p in l.palabras]
    return sum(p.confianza for p in pals) / len(pals) if pals else 0.0


def _a_original(lineas: list[Linea], t: preproceso.ImagenTrabajo) -> list[Linea]:
    """Cajas de vuelta a la imagen original (para el PDF buscable y la revisión)."""
    for l in lineas:
        for p in l.palabras:
            p.caja = t.a_original(p.caja)
    return lineas


def _reconocer(base: preproceso.ImagenTrabajo, motores: Motores, rapido: bool) -> tuple[list[Linea], list[str]]:
    """1) RapidOCR (rápido) sobre la imagen y, si la confianza es baja, sobre otras versiones;
    2) Tesseract UNA sola vez, sobre la mejor versión y solo en el idioma detectado; 3) votación.
    En modo rápido: solo RapidOCR sobre la imagen estándar."""
    usar_rapid = motores.rapid.disponible()
    variantes = ("estandar",) if rapido else preproceso.VARIANTES
    mejor_t, mejor_pr, mejor_conf = None, [], -1.0
    if usar_rapid:
        for nombre in variantes:
            t = preproceso.variante(base, nombre)
            pr = motores.rapid.reconocer(t.imagen)
            conf = sum(p.confianza for p in pr) / len(pr) if pr else 0.0
            if conf > mejor_conf:
                mejor_t, mejor_pr, mejor_conf = t, pr, conf
            if mejor_conf >= config.UMBRAL_PAGINA:
                break
    if mejor_t is None:
        mejor_t = preproceso.variante(base, "estandar")
    usados = [motores.rapid.nombre] if usar_rapid else []
    if rapido or not motores.tesseract.disponible():
        return _a_original(agrupar_en_lineas(mejor_pr), mejor_t), usados
    idioma = diccionarios().detectar_idioma([p.texto for p in mejor_pr])
    pt = motores.tesseract.reconocer(mejor_t.imagen, config.TESSERACT_POR_IDIOMA.get(idioma))
    usados.append(motores.tesseract.nombre)
    lineas = votar(mejor_pr, pt) if (mejor_pr and pt) else agrupar_en_lineas(mejor_pr or pt)
    return _a_original(lineas, mejor_t), usados


def procesar_pagina(
    pagina: Pagina, motores: Motores, lector_digital: LectorPdfDigital | None, rapido: bool = False
) -> ResultadoPagina:
    """`rapido`: solo RapidOCR, sin reintentos ni tablas (se usa si la página superó el tiempo límite)."""
    inicio = time.perf_counter()
    perfil = perfilar(pagina)

    escala = config.DPI_RENDER / 72
    palabras = lector_digital.palabras(pagina.indice, escala) if (
        perfil.tipo == TipoPagina.DIGITAL and lector_digital is not None
    ) else []
    if palabras and not texto_digital_legible(palabras):
        # Fuentes mal codificadas: el PDF "tiene texto" pero sale basura. Nunca se entrega: se usa OCR.
        perfil.tipo = TipoPagina.ESCANEO
        aviso_ilegible = "texto digital ilegible: se leyó con OCR"
    else:
        aviso_ilegible = ""
    if perfil.tipo == TipoPagina.DIGITAL and lector_digital is not None:
        lineas = agrupar_en_lineas(palabras)
        try:
            todas = [p for l in lineas for p in l.palabras]
            con_lineas = lector_digital.tablas(pagina.indice, escala)
            sin_lineas = []
            if len(todas) >= 8:  # tablas sin líneas: hace falta mirar la página como imagen
                dpi_zonas = 150  # suficiente para encontrar zonas; el texto es el exacto del PDF
                imagen, _ = pagina.imagen(dpi_zonas)
                sin_lineas = tablas.detectar_sin_bordes_digital(
                    imagen, todas, con_lineas, escala=config.DPI_RENDER / dpi_zonas
                )
            tablas_pag = tablas.finalizar(con_lineas + sin_lineas, todas)
        except Exception:
            log.exception("Tablas del PDF digital: se continúa sin ellas")
            tablas_pag = []
        return ResultadoPagina(
            perfil=perfil,
            lineas=lineas,
            estado=EstadoPagina.OK,
            motores=[LectorPdfDigital.nombre],
            confianza_media=1.0,
            segundos=round(time.perf_counter() - inicio, 2),
            idioma=diccionarios().detectar_idioma([p.texto for p in palabras]),
            tablas=tablas_pag,
        )

    base = preparar_imagen(pagina, perfil, motores)
    mejor_lineas, mejor_motores = _reconocer(base, motores, rapido)

    dic = diccionarios()
    for l in mejor_lineas:
        for p in l.palabras:
            if p.confianza < 0.98:
                corregir_palabra(p, dic)
    marcar_dudosas(mejor_lineas)
    estado = EstadoPagina.DUDOSA if any(p.dudosa for l in mejor_lineas for p in l.palabras) else EstadoPagina.OK
    palabras = [p.texto for l in mejor_lineas for p in l.palabras]
    tablas_pag = [] if rapido else _tablas_en_imagen(base, mejor_lineas)
    if rapido:
        aviso_ilegible = "; ".join(x for x in (aviso_ilegible, "leída en modo rápido (superó el tiempo límite)") if x)
    return ResultadoPagina(
        perfil=perfil,
        lineas=mejor_lineas,
        estado=estado,
        motores=mejor_motores,
        confianza_media=round(_confianza_media(mejor_lineas), 4),
        segundos=round(time.perf_counter() - inicio, 2),
        idioma=dic.detectar_idioma(palabras),
        mensaje="; ".join(([aviso_ilegible] if aviso_ilegible else []) + base.pasos),
        tablas=tablas_pag,
    )


def _tablas_en_imagen(base: preproceso.ImagenTrabajo, lineas: list[Linea]) -> list:
    """Detecta tablas en la imagen enderezada y devuelve sus cajas a la página original."""
    import cv2
    import numpy as np

    from .modelo import Palabra

    try:
        originales = [p for l in lineas for p in l.palabras]
        trabajo = []
        for p in originales:
            x0, y0, x1, y1 = p.caja
            pts = np.array([[[x0, y0]], [[x1, y0]], [[x1, y1]], [[x0, y1]]], dtype=np.float64)
            q = cv2.perspectiveTransform(pts, base.H).reshape(-1, 2)
            trabajo.append(Palabra(p.texto, p.confianza, (q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max())))
        encontradas = tablas.finalizar(tablas.detectar_en_imagen(base.imagen, trabajo), trabajo)
        for t in encontradas:
            t.caja = base.a_original(t.caja)
            for c in t.celdas:
                c.caja = base.a_original(c.caja)
        return encontradas
    except Exception:
        log.exception("Detección de tablas: se continúa sin ellas")
        return []


def _modo_rapido(ex: ThreadPoolExecutor, pagina: Pagina, motores: Motores, lector) -> ResultadoPagina:
    """Segunda oportunidad para una página lenta: solo RapidOCR. Si también falla, queda marcada."""
    inicio = time.perf_counter()
    fut = ex.submit(procesar_pagina, pagina, motores, lector, True)
    try:
        return fut.result(timeout=config.TIEMPO_LIMITE_RAPIDO_S)
    except Exception as e:  # noqa: BLE001
        log.warning("Modo rápido también falló en página %s: %s", pagina.numero, e)
        return _pagina_no_procesada(pagina, "Tiempo límite superado", time.perf_counter() - inicio)


def _pagina_no_procesada(pagina: Pagina, mensaje: str, segundos: float) -> ResultadoPagina:
    try:
        perfil = perfilar(pagina)
    except Exception:
        perfil = PerfilPagina(pagina.numero, TipoPagina.ESCANEO, 0, 0, config.DPI_RENDER, 595, 842)
    return ResultadoPagina(perfil, [], EstadoPagina.NO_PROCESADA, [], 0.0, round(segundos, 2), mensaje=mensaje)


def tiempo_limite_pagina() -> float:
    eq = hardware.detectar()
    factor = 1.0 if eq.nucleos >= 8 else 2.0
    return config.TIEMPO_LIMITE_BASE_S * factor


def procesar_documento(
    ruta: Path,
    contrasena: str | None = None,
    al_progresar: Callable[[Progreso], None] | None = None,
    control: Control | None = None,
    paginas: list[int] | None = None,
) -> ResultadoDocumento:
    """Procesa un documento completo. `paginas`: números (1-based) a reprocesar."""
    ruta = Path(ruta)
    control = control or Control()
    motores = Motores.obtener()
    inicio = time.perf_counter()
    limite = tiempo_limite_pagina()

    doc = Documento(ruta, contrasena)
    lector = None
    colgadas = 0  # páginas que superaron el tiempo límite y siguen ocupando un hilo
    ex = ThreadPoolExecutor(max_workers=hardware.detectar().paginas_en_paralelo + 1)
    try:
        total = len(doc)
        lector = LectorPdfDigital(ruta, contrasena) if doc.es_pdf else None
        if paginas:
            for n in paginas:
                borrar_cache_pagina(ruta, n)
        resultados: dict[int, ResultadoPagina] = {}
        paralelas = hardware.detectar().paginas_en_paralelo

        def avisar(evento: str, pagina: int, r: ResultadoPagina | None = None) -> None:
            if not al_progresar:
                return
            detalle: dict = {"evento": evento, "hechas": len(resultados)}
            if r is not None:
                detalle.update(
                    tipo=r.perfil.tipo.value,
                    motores=r.motores,
                    confianza=r.confianza_media,
                    pasos=r.mensaje,
                    estado=r.estado.value,
                    acelerador=motores.rapid.acelerador,
                    segundos=r.segundos,
                )
            al_progresar(Progreso(ruta, pagina, total, detalle))

        avisar("inicio", 0)  # la interfaz ya sabe cuántas páginas hay
        pendientes = list(range(total))
        activos: dict = {}  # futuro -> (índice, inicio)
        while pendientes or activos:
            # Mantener ocupados todos los hilos: apenas termina una página, entra la siguiente
            while pendientes and len(activos) < paralelas:
                control.esperar_si_pausado()
                i = pendientes.pop(0)
                cache = cargar_cache(ruta, i + 1)
                if cache is not None:
                    resultados[i] = cache
                    avisar("terminada", i + 1, cache)
                    continue
                activos[ex.submit(procesar_pagina, doc.pagina(i), motores, lector)] = (i, time.perf_counter())
                avisar("iniciada", i + 1)
            if not activos:
                continue
            ahora = time.perf_counter()
            espera = max(0.5, min(limite - (ahora - t0) for _, t0 in activos.values()))
            listos, _ = wait(list(activos), timeout=min(espera, 1.0), return_when=FIRST_COMPLETED)
            if control.cancelar.is_set():
                raise Cancelado()
            for fut in listos:
                i, t0 = activos.pop(fut)
                try:
                    r = fut.result()
                except Exception:  # un motor falló: segunda oportunidad en modo rápido
                    log.exception("Error en página %s: se relee en modo rápido", i + 1)
                    r = _modo_rapido(ex, doc.pagina(i), motores, lector)
                resultados[i] = r
                if r.estado != EstadoPagina.NO_PROCESADA:
                    guardar_cache(ruta, r)
                avisar("terminada", i + 1, r)
            for fut, (i, t0) in list(activos.items()):
                if time.perf_counter() - t0 >= limite:  # página colgada: se sigue con las demás
                    activos.pop(fut)
                    colgadas += 1
                    log.warning("Página %s superó el tiempo límite (%.0f s): se relee en modo rápido", i + 1, limite)
                    r = _modo_rapido(ex, doc.pagina(i), motores, lector)
                    resultados[i] = r
                    if r.estado != EstadoPagina.NO_PROCESADA:
                        guardar_cache(ruta, r)
                    avisar("terminada", i + 1, r)
    finally:
        # Con una página colgada NO se espera ni se cierra el documento: ese hilo aún podría
        # estar leyéndolo. Se libera al cerrar eh-ocr. Sin páginas colgadas, cierre normal.
        ex.shutdown(wait=colgadas == 0, cancel_futures=True)
        if colgadas == 0:
            if lector is not None:
                lector.cerrar()
            doc.cerrar()

    return ResultadoDocumento(
        origen=str(ruta),
        paginas=[resultados[i] for i in range(total)],
        segundos=round(time.perf_counter() - inicio, 2),
    )
