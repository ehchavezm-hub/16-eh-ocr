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

    def tablas(self, indice: int, escala: float) -> list:
        """Tablas con líneas del propio PDF (exactas). Cajas en píxeles (puntos × escala)."""
        from ..tablas import Celda, Tabla, _agrupar

        with self._lock:
            pagina = self._pdf.pages[indice]
            try:
                encontradas = pagina.find_tables()
                datos = [(t.bbox, [c for c in t.cells if c]) for t in encontradas]
            finally:
                pagina.close()
        salida = []
        for bbox, celdas_pt in datos:
            if len(celdas_pt) < 4:
                continue
            xs = _agrupar([v for c in celdas_pt for v in (c[0], c[2])], 2)
            ys = _agrupar([v for c in celdas_pt for v in (c[1], c[3])], 2)

            def idx(lista, v):
                return min(range(len(lista)), key=lambda k: abs(lista[k] - v))

            celdas = []
            for x0, top, x1, bottom in celdas_pt:
                c0, c1 = idx(xs, x0), idx(xs, x1)
                r0, r1 = idx(ys, top), idx(ys, bottom)
                if c1 <= c0 or r1 <= r0:
                    continue
                celdas.append(Celda(r0, c0, r1 - r0, c1 - c0, (x0 * escala, top * escala, x1 * escala, bottom * escala)))
            if celdas:
                caja = tuple(v * escala for v in bbox)
                salida.append(Tabla(caja, len(ys) - 1, len(xs) - 1, celdas, "pdf"))
        return salida

    def cerrar(self) -> None:
        self._pdf.close()
