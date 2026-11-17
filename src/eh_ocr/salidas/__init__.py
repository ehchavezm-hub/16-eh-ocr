"""Generadores de salida. Todos escriben de forma atómica y nunca sobrescriben."""

from __future__ import annotations

import logging
from pathlib import Path

from ..archivos import carpeta_salida, ruta_unica
from ..modelo import ResultadoDocumento
from . import docx_salida, json_salida, pdf_buscable, texto, xlsx_salida

FORMATOS = {
    "pdf": ("PDF buscable", ".pdf"),
    "docx": ("Word (DOCX)", ".docx"),
    "xlsx": ("Excel (XLSX)", ".xlsx"),
    "txt": ("Texto (TXT)", ".txt"),
    "md": ("Markdown", ".md"),
    "json": ("JSON", ".json"),
}
FORMATOS_POR_DEFECTO = ("pdf", "docx")

log = logging.getLogger(__name__)


def generar(
    resultado: ResultadoDocumento,
    formatos: tuple[str, ...] | list[str],
    carpeta: Path | None = None,
    contrasena: str | None = None,
    errores: list[str] | None = None,
) -> list[Path]:
    """Genera los formatos pedidos. Si uno falla, los demás se generan igual y el fallo
    queda en `errores` (nombre del formato y motivo), nunca a medias en disco."""
    origen = Path(resultado.origen)
    destino_dir = carpeta_salida(origen, carpeta)
    base = f"{origen.stem}_ocr"
    salidas: list[Path] = []
    for f in formatos:
        if f not in FORMATOS:
            continue
        destino = ruta_unica(destino_dir, base, FORMATOS[f][1])
        try:
            _escribir(f, resultado, destino, contrasena)
        except Exception as e:  # noqa: BLE001
            log.exception("No se pudo generar %s", f)
            if errores is not None:
                errores.append(f"{FORMATOS[f][0]}: {e}")
            continue
        salidas.append(destino)
    resultado.salidas = [str(s) for s in salidas]
    return salidas


def _escribir(f: str, resultado: ResultadoDocumento, destino: Path, contrasena: str | None) -> None:
    escritores = {
        "txt": lambda: texto.escribir_txt(resultado, destino),
        "md": lambda: texto.escribir_md(resultado, destino),
        "json": lambda: json_salida.escribir(resultado, destino),
        "xlsx": lambda: xlsx_salida.escribir(resultado, destino),
        "docx": lambda: docx_salida.escribir(resultado, destino),
        "pdf": lambda: pdf_buscable.escribir(resultado, destino, contrasena),
    }
    escritores[f]()
