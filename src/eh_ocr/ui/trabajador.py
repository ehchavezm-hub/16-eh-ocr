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
    estado: Estado = Estado.COLA
    paginas: int = 0
    pagina_actual: int = 0
    confianza: float | None = None
    mensaje: str = ""
    contrasena: str | None = None
    resultado: ResultadoDocumento | None = None
    salidas: list[Path] = field(default_factory=list)
    detalle: dict = field(default_factory=dict)

    @property
    def terminado(self) -> bool:
        return self.estado in (Estado.LISTO, Estado.DUDOSO)


class Trabajador(QObject):
    trabajo_cambiado = Signal(int)
    progreso_total = Signal(int, int)       # páginas hechas, páginas totales (conocidas)
    pide_contrasenas = Signal(list)         # índices de trabajos protegidos
    cola_terminada = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.trabajos: list[Trabajo] = []
        self.formatos: tuple[str, ...] = salidas.FORMATOS_POR_DEFECTO
        self.carpeta: Path | None = None
        self.control = pipeline.Control()
        self._hilo: threading.Thread | None = None
        self._lock = threading.Lock()

    # --- API para la interfaz ----------------------------------------------
    def agregar(self, rutas: list[Path]) -> list[int]:
        nuevos = []
        with self._lock:
            for r in rutas:
                t = Trabajo(Path(r))
                if t.ruta.suffix.lower() in EXT_HEIC:
                    t.estado = Estado.NO_ADMITIDO
                    t.mensaje = "Formato HEIC: guarda o comparte la foto como JPG"
                self.trabajos.append(t)
                nuevos.append(len(self.trabajos) - 1)
        return nuevos

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
        hechas = sum(t.pagina_actual for t in self.trabajos)
        total = sum(t.paginas for t in self.trabajos)
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
        t.estado = Estado.PROCESANDO
        t.pagina_actual = 0
        self.trabajo_cambiado.emit(i)

        def al_progresar(p: pipeline.Progreso) -> None:
            t.paginas = p.total
            t.pagina_actual = max(t.pagina_actual, p.pagina)
            t.detalle = dict(p.detalle, pagina=p.pagina)
            self.trabajo_cambiado.emit(i)
            self.progreso_total.emit(*self.paginas_totales())

        try:
            r = pipeline.procesar_documento(t.ruta, t.contrasena, al_progresar, self.control)
            t.resultado = r
            t.salidas = salidas.generar(r, self.formatos, self.carpeta, t.contrasena)
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
                    partes.append(f"{n_dudosas} palabras dudosas")
                if n_no:
                    partes.append(f"{n_no} páginas no procesadas")
                t.mensaje = ", ".join(partes)
            else:
                t.estado = Estado.LISTO
                t.mensaje = ""
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
