"""Tesseract (Apache 2.0): segundo motor para la votación y detector de orientación.

Se ejecuta como proceso aparte, sin ventana de consola.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from .. import config
from ..modelo import Palabra
from .base import Motor, MotorNoDisponible

_SIN_VENTANA = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


class MotorTesseract(Motor):
    nombre = "Tesseract"

    def __init__(self, idiomas: str = config.IDIOMAS_TESSERACT, tiempo_limite: float = 180) -> None:
        self.idiomas = idiomas
        self.tiempo_limite = tiempo_limite
        self._exe = config.ruta_tesseract()

    def disponible(self) -> bool:
        return self._exe is not None and self._exe.exists()

    def _entorno(self) -> dict:
        env = dict(os.environ)
        td = config.carpeta_tessdata()
        if td is not None:
            env["TESSDATA_PREFIX"] = str(td)
        env["OMP_THREAD_LIMIT"] = "2"
        return env

    def _ejecutar(self, imagen: np.ndarray, argumentos: list[str]) -> str:
        if not self.disponible():
            raise MotorNoDisponible("Tesseract no está incluido.")
        with tempfile.TemporaryDirectory(prefix="eh-ocr-") as d:
            ruta = Path(d) / "pagina.png"
            cv2.imwrite(str(ruta), cv2.cvtColor(imagen, cv2.COLOR_RGB2BGR))
            proc = subprocess.run(
                [str(self._exe), str(ruta), "stdout", *argumentos],
                capture_output=True,
                env=self._entorno(),
                timeout=self.tiempo_limite,
                creationflags=_SIN_VENTANA,
            )
        if proc.returncode != 0:
            raise MotorNoDisponible(proc.stderr.decode("utf-8", "replace")[-500:])
        return proc.stdout.decode("utf-8", "replace")

    def reconocer(self, imagen: np.ndarray) -> list[Palabra]:
        salida = self._ejecutar(imagen, ["-l", self.idiomas, "--oem", "1", "--psm", "3", "tsv"])
        palabras: list[Palabra] = []
        lector = csv.DictReader(io.StringIO(salida), delimiter="\t", quoting=csv.QUOTE_NONE)
        for fila in lector:
            if fila.get("level") != "5":
                continue
            texto = (fila.get("text") or "").strip()
            conf = float(fila.get("conf") or -1)
            if not texto or conf < 0:
                continue
            x, y = float(fila["left"]), float(fila["top"])
            w, h = float(fila["width"]), float(fila["height"])
            palabras.append(Palabra(texto, conf / 100.0, (x, y, x + w, y + h), self.nombre))
        return palabras

    def orientacion(self, imagen: np.ndarray) -> tuple[int, float]:
        """(grados a rotar en sentido horario para enderezar, confianza)."""
        try:
            salida = self._ejecutar(imagen, ["--psm", "0", "-l", "osd"])
        except Exception:
            return 0, 0.0
        rot = re.search(r"Rotate:\s*(\d+)", salida)
        conf = re.search(r"Orientation confidence:\s*([\d.]+)", salida)
        if not rot:
            return 0, 0.0
        return int(rot.group(1)) % 360, float(conf.group(1)) if conf else 0.0
