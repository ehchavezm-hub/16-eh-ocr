"""Generadores de salida. Todos escriben de forma atómica y nunca sobrescriben."""

from __future__ import annotations

from pathlib import Path

from ..archivos import carpeta_salida, ruta_unica
from ..modelo import ResultadoDocumento
from . import docx_salida, json_salida, pdf_buscable, texto

FORMATOS = {
    "pdf": ("PDF buscable", ".pdf"),
    "docx": ("Word (DOCX)", ".docx"),
    "txt": ("Texto (TXT)", ".txt"),
    "md": ("Markdown", ".md"),
    "json": ("JSON", ".json"),
}
FORMATOS_POR_DEFECTO = ("pdf", "docx")


def generar(
    resultado: ResultadoDocumento,
    formatos: tuple[str, ...] | list[str],
    carpeta: Path | None = None,
    contrasena: str | None = None,
) -> list[Path]:
    origen = Path(resultado.origen)
    destino_dir = carpeta_salida(origen, carpeta)
    base = f"{origen.stem}_ocr"
    salidas: list[Path] = []
    for f in formatos:
        if f not in FORMATOS:
            continue
        destino = ruta_unica(destino_dir, base, FORMATOS[f][1])
        if f == "txt":
            texto.escribir_txt(resultado, destino)
        elif f == "md":
            texto.escribir_md(resultado, destino)
        elif f == "json":
            json_salida.escribir(resultado, destino)
        elif f == "docx":
            docx_salida.escribir(resultado, destino)
        elif f == "pdf":
            pdf_buscable.escribir(resultado, destino, contrasena)
        salidas.append(destino)
    resultado.salidas = [str(s) for s in salidas]
    return salidas
