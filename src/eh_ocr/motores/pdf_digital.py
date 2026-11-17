"""Texto digital de PDF (pdfplumber): exacto e instantáneo, sin OCR."""

from __future__ import annotations

import threading
from pathlib import Path

import pdfplumber

from ..modelo import Palabra


class LectorPdfDigital:
    nombre = "PDF digital"

    def __init__(self, ruta: Path, contrasena: str | None = None) -> None:
        self._pdf = pdfplumber.open(str(ruta), password=contrasena or "")
        self._lock = threading.Lock()

    def palabras(self, indice: int, escala: float) -> list[Palabra]:
        """Palabras de la página con cajas en píxeles (puntos × escala)."""
        with self._lock:
            pagina = self._pdf.pages[indice]
            palabras = pagina.extract_words(keep_blank_chars=False, use_text_flow=True)
            pagina.close()
        salida = []
        for w in palabras:
            caja = (w["x0"] * escala, w["top"] * escala, w["x1"] * escala, w["bottom"] * escala)
            salida.append(Palabra(w["text"], 1.0, caja, self.nombre))
        return salida

    def cerrar(self) -> None:
        self._pdf.close()
