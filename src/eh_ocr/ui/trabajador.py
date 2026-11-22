"""Cola de trabajos que se procesa en segundo plano sin congelar la ventana."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .. import pipeline, salidas
from ..documento import EXT_HEIC, ErrorContrasena, ErrorDocumento, FormatoNoAdmitido
from ..modelo import ResultadoDocumento

log = logging.getLogger(__name__)


class Estado(str, Enum):
    PENDIENTE = "Listo para procesar"
    COLA = "En cola"
    PROCESANDO = "Procesando"
    LISTO = "Listo"
    DUDOSO = "Listo, con zonas dudosas"
    PROTEGIDO = "Pedirá contraseña al final"
    NO_ADMITIDO = "Formato no admitido"
    ERROR = "Error"
    CANCELADO = "Cancelado"


@dataclass
class Trabajo:
    ruta: Path
    estado: Estado = Estado.PENDIENTE
    marcado: bool = True
    paginas: int = 0
    pagina_actual: int = 0
    confianza: float | None = None
    mensaje: str = ""
    contrasena: str | None = None
    resultado: ResultadoDocumento | None = None
    salidas: list[Path] = field(default_factory=list)
    detalle: dict = field(default_factory=dict)
    en_curso: set = field(default_factory=set)   # páginas que se están leyendo ahora
    inicio: float = 0.0                           # para estimar el tiempo restante

    def restante_s(self) -> float | None:
        """Segundos estimados para terminar este documento (None si aún no se puede estimar)."""
        if not self.inicio or self.pagina_actual <= 0 or not self.paginas:
            return None
        import time

        por_pagina = (time.monotonic() - self.inicio) / self.pagina_actual
        return por_pagina * (self.paginas - self.pagina_actual)

    @property
    def terminado(self) -> bool:
        return self.estado in (Estado.LISTO, Estado.DUDOSO)


def _clave(ruta: Path) -> str:
    """Identidad de un archivo para no repetirlo en la lista (sin distinguir mayúsculas en Windows)."""
    try:
        r = str(Path(ruta).resolve())
    except OSError:
        r = str(Path(ruta).absolute())
    import os

    return os.path.normcase(r)


class Trabajador(QObject):
    trabajo_cambiado = Signal(int)
    progreso_total = Signal(int, int)       # páginas hechas, páginas totales (conocidas)
    pide_contrasenas = Signal(list)         # índices de trabajos protegidos
    cola_terminada = Signal()
    lista_cambiada = Signal()               # se quitaron archivos: los índices cambiaron

    def __init__(self) -> None:
        super().__init__()
        self.trabajos: list[Trabajo] = []
        self.formatos: tuple[str, ...] = salidas.FORMATOS_POR_DEFECTO
        self.carpeta: Path | None = None
        self.control = pipeline.Control()
        self._hilo: threading.Thread | None = None
        self._lock = threading.Lock()

    # --- API para la interfaz ----------------------------------------------
    def agregar(self, rutas: list[Path]) -> tuple[list[int], int]:
        """Agrega a la lista SIN procesar. Devuelve (índices nuevos, cantidad de repetidos)."""
        nuevos, repetidos = [], 0
        with self._lock:
            existentes = {_clave(t.ruta) for t in self.trabajos}
            for r in rutas:
                clave = _clave(Path(r))
                if clave in existentes:
                    repetidos += 1
                    continue
                existentes.add(clave)
                t = Trabajo(Path(r))
                if t.ruta.suffix.lower() in EXT_HEIC:
                    t.estado = Estado.NO_ADMITIDO
                    t.marcado = False
                    t.mensaje = "Formato HEIC: guarda o comparte la foto como JPG"
                self.trabajos.append(t)
                nuevos.append(len(self.trabajos) - 1)
        return nuevos, repetidos

    def marcados_procesables(self) -> list[int]:
        return [
            i for i, t in enumerate(self.trabajos)
            if t.marcado and t.estado not in (Estado.PROCESANDO, Estado.COLA, Estado.NO_ADMITIDO)
        ]

    def procesar_marcados(self) -> int:
        """Pone en cola los archivos marcados y arranca. Devuelve cuántos se encolaron."""
        indices = self.marcados_procesables()
        with self._lock:
            for i in indices:
                t = self.trabajos[i]
                t.estado = Estado.COLA
                t.mensaje = ""
                t.pagina_actual = 0
        for i in indices:
            self.trabajo_cambiado.emit(i)
        if indices:
            self.iniciar()
        return len(indices)

    def quitar(self, indices: list[int]) -> int:
        """Quita de la lista (no borra archivos). No se permite mientras se procesa: la numeración
        de la lista la usa el proceso en curso para informar el avance."""
        if self.ocupado:
            return 0
        with self._lock:
            quitar = {i for i in indices if 0 <= i < len(self.trabajos)}
            self.trabajos = [t for i, t in enumerate(self.trabajos) if i not in quitar]
        if quitar:
            self.lista_cambiada.emit()
        return len(quitar)

    def iniciar(self) -> None:
        if self.ocupado:
            return
        self.control = pipeline.Control()
        self._hilo = threading.Thread(target=self._ejecutar, name="eh-ocr-cola", daemon=True)
        self._hilo.start()

    @property
    def ocupado(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def pausar(self, pausado: bool) -> None:
        if pausado:
            self.control.reanudar.clear()
        else:
            self.control.reanudar.set()

    def cancelar(self) -> None:
        self.control.cancelar.set()
        self.control.reanudar.set()

    def reintentar_con_contrasena(self, indice: int, contrasena: str) -> None:
        t = self.trabajos[indice]
        t.contrasena = contrasena
        t.estado = Estado.COLA
        t.mensaje = ""
        self.trabajo_cambiado.emit(indice)

    def paginas_totales(self) -> tuple[int, int]:
        """Progreso de la tanda en curso (archivos en cola, procesando o ya procesados en ella)."""
        en_tanda = [t for t in self.trabajos if t.estado != Estado.PENDIENTE]
        hechas = sum(t.pagina_actual for t in en_tanda)
        total = sum(t.paginas for t in en_tanda)
        return hechas, total

    # --- hilo de trabajo ---------------------------------------------------
    def _ejecutar(self) -> None:
        protegidos: list[int] = []
        try:
            while True:
                with self._lock:
                    pendientes = [i for i, t in enumerate(self.trabajos) if t.estado == Estado.COLA]
                if not pendientes:
                    break
                i = pendientes[0]
                if self.control.cancelar.is_set():
                    for k in pendientes:
                        self.trabajos[k].estado = Estado.CANCELADO
                        self.trabajo_cambiado.emit(k)
                    break
                self._procesar(i, protegidos)
        finally:
            if protegidos and not self.control.cancelar.is_set():
                self.pide_contrasenas.emit(protegidos)
            self.cola_terminada.emit()

    def _procesar(self, i: int, protegidos: list[int]) -> None:
        t = self.trabajos[i]
        import time

        t.estado = Estado.PROCESANDO
        t.pagina_actual = 0
        t.en_curso = set()
        t.inicio = time.monotonic()
        self.trabajo_cambiado.emit(i)

        def al_progresar(p: pipeline.Progreso) -> None:
            t.paginas = p.total
            evento = p.detalle.get("evento")
            if evento == "iniciada":
                t.en_curso.add(p.pagina)
            elif evento == "terminada":
                t.en_curso.discard(p.pagina)
                t.pagina_actual = p.detalle.get("hechas", t.pagina_actual + 1)
                t.detalle = dict(p.detalle, pagina=p.pagina)
            self.trabajo_cambiado.emit(i)
            self.progreso_total.emit(*self.paginas_totales())

        try:
            r = pipeline.procesar_documento(t.ruta, t.contrasena, al_progresar, self.control)
            t.resultado = r
            errores: list[str] = []
            t.salidas = salidas.generar(r, self.formatos, self.carpeta, t.contrasena, errores)
            pals = [w for p in r.paginas for w in p.palabras]
            t.confianza = r.confianza_media if pals else None
            t.paginas = len(r.paginas)
            t.pagina_actual = t.paginas
            n_dudosas = sum(len(p.dudosas) for p in r.paginas)
            n_no = len(r.paginas_no_procesadas)
            if n_dudosas or n_no:
                t.estado = Estado.DUDOSO
                partes = []
                if n_dudosas:
                    partes.append(f"{n_dudosas} palabra{'s' if n_dudosas != 1 else ''} dudosa{'s' if n_dudosas != 1 else ''}")
                if n_no:
                    partes.append(f"{n_no} página{'s' if n_no != 1 else ''} no procesada{'s' if n_no != 1 else ''}")
                t.mensaje = ", ".join(partes)
            else:
                t.estado = Estado.LISTO
                t.mensaje = ""
            if errores:
                t.estado = Estado.DUDOSO
                aviso = "no se pudo crear " + "; ".join(errores)
                t.mensaje = f"{t.mensaje}, {aviso}" if t.mensaje else aviso
        except pipeline.Cancelado:
            t.estado = Estado.CANCELADO
            t.mensaje = "Se retomará donde quedó si lo vuelves a procesar"
        except ErrorContrasena as e:
            t.estado = Estado.PROTEGIDO
            t.mensaje = str(e)
            protegidos.append(i)
        except FormatoNoAdmitido as e:
            t.estado = Estado.NO_ADMITIDO
            t.mensaje = str(e)
        except ErrorDocumento as e:
            t.estado = Estado.ERROR
            t.mensaje = str(e)
        except Exception as e:  # nunca se cierra la app por un archivo
            log.exception("Fallo procesando un archivo")
            t.estado = Estado.ERROR
            t.mensaje = f"Error inesperado: {e}"
        self.trabajo_cambiado.emit(i)
        self.progreso_total.emit(*self.paginas_totales())
