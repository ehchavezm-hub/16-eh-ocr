"""RapidOCR (PP-OCRv6 en ONNX): motor principal para texto impreso.

- Usa los modelos *medium* (más precisos) si están incluidos en el paquete;
  si no, los *small* que trae la librería.
- Acelera con DirectML (cualquier gráfica de Windows) y vuelve a CPU si falla.
- El clasificador de orientación por línea está DESACTIVADO: en pruebas
  invertía líneas correctas. La orientación se corrige por página.
"""

from __future__ import annotations

import logging
import queue
import threading

import numpy as np

from .. import config, hardware
from ..modelo import Palabra
from .base import Motor, MotorNoDisponible

log = logging.getLogger(__name__)


class MotorRapid(Motor):
    nombre = "RapidOCR"

    def __init__(self) -> None:
        self._motor = None  # primera instancia (y configuración elegida)
        self._config: tuple[bool, bool] | None = None
        self._lock = threading.Lock()
        self._libres: queue.Queue = queue.Queue()
        self._creadas = 0
        self.acelerador = "CPU"
        self.modelos = "small"

    @staticmethod
    def instancias_maximas() -> int:
        """Una instancia por página en paralelo (cada una ocupa ~0,5 GB con los modelos medium)."""
        return hardware.detectar().paginas_en_paralelo

    def disponible(self) -> bool:
        try:
            self._cargar()
            return True
        except MotorNoDisponible:
            return False

    def _parametros(self, usar_dml: bool, usar_medium: bool = True) -> dict:
        p = {
            "Global.log_level": "error",
            "Global.use_cls": False,
            "Global.return_word_box": True,
            "Global.max_side_len": 4000,
            "Global.text_score": 0.3,
            "Det.box_thresh": 0.5,
            "Det.unclip_ratio": 1.6,
            "EngineConfig.onnxruntime.use_dml": usar_dml,
        }
        carpeta = config.carpeta_modelos() / "rapidocr"
        det = carpeta / "PP-OCRv6_det_medium.onnx"
        rec = carpeta / "PP-OCRv6_rec_medium.onnx"
        self.modelos = "small"
        if usar_medium and det.exists() and rec.exists():
            from rapidocr.utils.typings import ModelType

            p.update(
                {
                    "Det.model_type": ModelType.MEDIUM,
                    "Det.model_path": str(det),
                    "Rec.model_type": ModelType.MEDIUM,
                    "Rec.model_path": str(rec),
                }
            )
            self.modelos = "medium"
        return p

    def _cargar(self):
        if self._motor is not None:
            return self._motor
        with self._lock:
            if self._motor is not None:
                return self._motor
            try:
                from rapidocr import RapidOCR
            except Exception as e:  # pragma: no cover
                raise MotorNoDisponible(f"RapidOCR no está incluido: {e}") from e
            usar_dml = hardware.detectar().acelerador == "DirectML"
            # Del más rápido y preciso al más seguro: nunca se queda sin motor.
            intentos = [(usar_dml, True), (False, True), (False, False)] if usar_dml else [(False, True), (False, False)]
            ultimo_error: Exception | None = None
            for dml, medium in intentos:
                try:
                    self._motor = RapidOCR(params=self._parametros(dml, medium))
                    self.acelerador = "DirectML" if dml else "CPU"
                    self._config = (dml, medium)
                    self._creadas = 1
                    self._libres.put(self._motor)
                    break
                except Exception as e:
                    log.warning("RapidOCR (DirectML=%s, medium=%s) falló: %s", dml, medium, e)
                    ultimo_error = e
            if self._motor is None:
                raise MotorNoDisponible(f"RapidOCR no pudo iniciarse: {ultimo_error}")
            return self._motor

    def _tomar(self):
        """Una instancia libre; si no hay y queda cupo, se crea otra (páginas en paralelo)."""
        self._cargar()
        try:
            return self._libres.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            crear = self._creadas < self.instancias_maximas()
            if crear:
                self._creadas += 1
        if crear:
            try:
                from rapidocr import RapidOCR

                return RapidOCR(params=self._parametros(*self._config))
            except Exception as e:  # sin memoria u otro problema: se comparte una existente
                log.warning("No se pudo crear otra instancia de RapidOCR: %s", e)
                with self._lock:
                    self._creadas -= 1
        return self._libres.get()

    def reconocer(self, imagen: np.ndarray) -> list[Palabra]:
        # Cada instancia de RapidOCR guarda estado por llamada: una página por instancia a la vez.
        motor = self._tomar()
        try:
            r = motor(imagen)
        finally:
            self._libres.put(motor)
        palabras: list[Palabra] = []
        if r is None or r.txts is None:
            return palabras
        word_results = r.word_results or ()
        for i, (txt, score, box) in enumerate(zip(r.txts, r.scores, r.boxes)):
            palabras_linea = word_results[i] if i < len(word_results) else ()
            if palabras_linea:
                for texto, conf, caja in palabras_linea:
                    texto = str(texto).strip()
                    if not texto:
                        continue
                    xs = [p[0] for p in caja]
                    ys = [p[1] for p in caja]
                    palabras.append(
                        Palabra(texto, float(conf), (min(xs), min(ys), max(xs), max(ys)), self.nombre)
                    )
            else:
                palabras.extend(_repartir_linea(str(txt), float(score), np.asarray(box), self.nombre))
        return palabras


def _repartir_linea(texto: str, conf: float, caja: np.ndarray, motor: str) -> list[Palabra]:
    """Si no hay cajas por palabra, reparte la línea proporcionalmente."""
    tokens = texto.split()
    if not tokens:
        return []
    x0, y0 = caja[:, 0].min(), caja[:, 1].min()
    x1, y1 = caja[:, 0].max(), caja[:, 1].max()
    total = sum(len(t) for t in tokens) + len(tokens) - 1
    ancho = (x1 - x0) / max(total, 1)
    salida, pos = [], 0
    for t in tokens:
        a = x0 + pos * ancho
        salida.append(Palabra(t, conf, (float(a), float(y0), float(a + len(t) * ancho), float(y1)), motor))
        pos += len(t) + 1
    return salida
