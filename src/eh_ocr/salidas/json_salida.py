"""Salida JSON con toda la estructura: páginas, líneas, palabras, cajas y confianza."""

from __future__ import annotations

import json
from pathlib import Path

from .. import __version__
from ..archivos import escribir_atomico
from ..modelo import ResultadoDocumento


def escribir(r: ResultadoDocumento, destino: Path) -> None:
    datos = {
        "eh_ocr": __version__,
        "origen": Path(r.origen).name,
        "segundos": r.segundos,
        "confianza_media": round(r.confianza_media, 4),
        "paginas_dudosas": r.paginas_dudosas,
        "paginas_no_procesadas": r.paginas_no_procesadas,
        "paginas": [p.a_dict() for p in r.paginas],
        "nota_coordenadas": "cajas en píxeles de la página a la resolución perfil.dpi; origen arriba-izquierda",
    }
    escribir_atomico(destino, json.dumps(datos, ensure_ascii=False, indent=1))
