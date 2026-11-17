"""Salidas TXT y Markdown."""

from __future__ import annotations

from pathlib import Path

from ..archivos import escribir_atomico
from ..modelo import EstadoPagina, ResultadoDocumento


def escribir_txt(r: ResultadoDocumento, destino: Path) -> None:
    partes = []
    for p in r.paginas:
        if p.estado == EstadoPagina.NO_PROCESADA:
            partes.append(f"[Página {p.perfil.numero}: no procesada — {p.mensaje}]")
        else:
            partes.append(p.texto)
    escribir_atomico(destino, "\n\f\n".join(partes) + "\n")


def _escapar_md(t: str) -> str:
    for c in "\\`*_[]#|":
        t = t.replace(c, "\\" + c)
    return t


def escribir_md(r: ResultadoDocumento, destino: Path) -> None:
    lineas = [f"# {_escapar_md(Path(r.origen).name)}", ""]
    for p in r.paginas:
        lineas.append(f"## Página {p.perfil.numero}")
        lineas.append("")
        if p.estado == EstadoPagina.NO_PROCESADA:
            lineas.append(f"> No procesada: {_escapar_md(p.mensaje)}")
        else:
            for l in p.lineas:
                lineas.append(
                    " ".join(
                        f"=={_escapar_md(w.texto)}==" if w.dudosa else _escapar_md(w.texto) for w in l.palabras
                    )
                    + "  "
                )
        lineas.append("")
    if any(p.dudosas for p in r.paginas):
        lineas.append("---")
        lineas.append("Las palabras marcadas con ==así== tienen baja confianza y conviene revisarlas.")
    escribir_atomico(destino, "\n".join(lineas) + "\n")
