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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, hardware, preproceso
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

VERSION_CACHE = 1


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

def id_trabajo(ruta: Path) -> str:
    st = Path(ruta).stat()
    clave = f"{Path(ruta).resolve()}|{st.st_size}|{st.st_mtime_ns}|v{VERSION_CACHE}"
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


def _reconocer_variante(t: preproceso.ImagenTrabajo, motores: Motores) -> tuple[list[Linea], list[str]]:
    usados = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_r = ex.submit(motores.rapid.reconocer, t.imagen) if motores.rapid.disponible() else None
        fut_t = ex.submit(motores.tesseract.reconocer, t.imagen) if motores.tesseract.disponible() else None
        pr = fut_r.result() if fut_r else []
        pt = fut_t.result() if fut_t else []
    if fut_r:
        usados.append(motores.rapid.nombre)
    if fut_t:
        usados.append(motores.tesseract.nombre)
    if pr and pt:
        lineas = votar(pr, pt)
    else:
        lineas = agrupar_en_lineas(pr or pt)
    # cajas de vuelta a la imagen original (para el PDF buscable y la revisión)
    for l in lineas:
        for p in l.palabras:
            p.caja = t.a_original(p.caja)
    return lineas, usados


def procesar_pagina(pagina: Pagina, motores: Motores, lector_digital: LectorPdfDigital | None) -> ResultadoPagina:
    inicio = time.perf_counter()
    perfil = perfilar(pagina)

    if perfil.tipo == TipoPagina.DIGITAL and lector_digital is not None:
        escala = config.DPI_RENDER / 72
        palabras = lector_digital.palabras(pagina.indice, escala)
        lineas = agrupar_en_lineas(palabras)
        return ResultadoPagina(
            perfil=perfil,
            lineas=lineas,
            estado=EstadoPagina.OK,
            motores=[LectorPdfDigital.nombre],
            confianza_media=1.0,
            segundos=round(time.perf_counter() - inicio, 2),
            idioma=diccionarios().detectar_idioma([p.texto for p in palabras]),
        )

    base = preparar_imagen(pagina, perfil, motores)
    mejor_lineas, mejor_motores, mejor_conf = [], [], -1.0
    for nombre in preproceso.VARIANTES:
        t = preproceso.variante(base, nombre)
        lineas, usados = _reconocer_variante(t, motores)
        conf = _confianza_media(lineas)
        if conf > mejor_conf:
            mejor_lineas, mejor_motores, mejor_conf = lineas, usados, conf
        if mejor_conf >= config.UMBRAL_PAGINA:
            break

    dic = diccionarios()
    for l in mejor_lineas:
        for p in l.palabras:
            if p.confianza < 0.98:
                corregir_palabra(p, dic)
    marcar_dudosas(mejor_lineas)
    estado = EstadoPagina.DUDOSA if any(p.dudosa for l in mejor_lineas for p in l.palabras) else EstadoPagina.OK
    palabras = [p.texto for l in mejor_lineas for p in l.palabras]
    return ResultadoPagina(
        perfil=perfil,
        lineas=mejor_lineas,
        estado=estado,
        motores=mejor_motores,
        confianza_media=round(_confianza_media(mejor_lineas), 4),
        segundos=round(time.perf_counter() - inicio, 2),
        idioma=dic.detectar_idioma(palabras),
        mensaje="; ".join(base.pasos),
    )


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

    with Documento(ruta, contrasena) as doc:
        total = len(doc)
        lector = LectorPdfDigital(ruta, contrasena) if doc.es_pdf else None
        if paginas:
            for n in paginas:
                borrar_cache_pagina(ruta, n)
        resultados: dict[int, ResultadoPagina] = {}
        paralelas = hardware.detectar().paginas_en_paralelo
        try:
            with ThreadPoolExecutor(max_workers=paralelas) as ex:
                pendientes = list(range(total))
                while pendientes:
                    control.esperar_si_pausado()
                    lote, pendientes = pendientes[:paralelas], pendientes[paralelas:]
                    futuros = {}
                    for i in lote:
                        cache = cargar_cache(ruta, i + 1)
                        if cache is not None:
                            resultados[i] = cache
                            continue
                        futuros[i] = (ex.submit(procesar_pagina, doc.pagina(i), motores, lector), time.perf_counter())
                    for i, (fut, t0) in futuros.items():
                        restante = max(1.0, limite - (time.perf_counter() - t0))
                        try:
                            r = fut.result(timeout=restante)
                        except FuturoTimeout:
                            r = _pagina_no_procesada(doc.pagina(i), "Tiempo límite superado", limite)
                        except Exception as e:  # el motor falló: no se cierra la app
                            log.exception("Error en página %s", i + 1)
                            r = _pagina_no_procesada(doc.pagina(i), f"Error: {e}", time.perf_counter() - t0)
                        resultados[i] = r
                        if r.estado != EstadoPagina.NO_PROCESADA:
                            guardar_cache(ruta, r)
                    for i in lote:
                        r = resultados[i]
                        if al_progresar:
                            al_progresar(
                                Progreso(
                                    ruta,
                                    i + 1,
                                    total,
                                    {
                                        "tipo": r.perfil.tipo.value,
                                        "motores": r.motores,
                                        "confianza": r.confianza_media,
                                        "pasos": r.mensaje,
                                        "estado": r.estado.value,
                                        "acelerador": motores.rapid.acelerador,
                                    },
                                )
                            )
        finally:
            if lector is not None:
                lector.cerrar()

    return ResultadoDocumento(
        origen=str(ruta),
        paginas=[resultados[i] for i in range(total)],
        segundos=round(time.perf_counter() - inicio, 2),
    )
