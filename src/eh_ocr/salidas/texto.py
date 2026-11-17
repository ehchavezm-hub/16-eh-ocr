"""Salidas TXT y Markdown."""

from __future__ import annotations

from pathlib import Path

from ..archivos import escribir_atomico
from ..modelo import EstadoPagina, ResultadoDocumento, ResultadoPagina
from ..tablas import Tabla, texto_celda


def _matriz(t: Tabla, palabras) -> list[list[str]]:
    """Tabla como matriz de textos; una celda combinada aparece en su primera posición."""
    m = [["" for _ in range(t.n_cols)] for _ in range(t.n_filas)]
    for c in t.celdas:
        if c.fila < t.n_filas and c.col < t.n_cols:
            m[c.fila][c.col] = texto_celda(c, palabras)
    return m


def _texto_pagina(p: ResultadoPagina) -> str:
    salida = []
    for tipo, b in p.bloques():
        if tipo == "tabla":
            salida.extend("\t".join(fila) for fila in _matriz(b, p.palabras))
        else:
            salida.append(b.texto)
    return "\n".join(salida)


def escribir_txt(r: ResultadoDocumento, destino: Path) -> None:
    partes = []
    for p in r.paginas:
        if p.estado == EstadoPagina.NO_PROCESADA:
            partes.append(f"[Página {p.perfil.numero}: no procesada — {p.mensaje}]")
        else:
            partes.append(_texto_pagina(p))
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
            for tipo, b in p.bloques():
                if tipo == "tabla":
                    m = _matriz(b, p.palabras)
                    lineas.append("")
                    for k, fila in enumerate(m):
                        lineas.append("| " + " | ".join(_escapar_md(t) for t in fila) + " |")
                        if k == 0:
                            lineas.append("|" + "---|" * len(fila))
                    lineas.append("")
                    continue
                lineas.append(
                    " ".join(
                        f"=={_escapar_md(w.texto)}==" if w.dudosa else _escapar_md(w.texto) for w in b.palabras
                    )
                    + "  "
                )
        lineas.append("")
    if any(p.dudosas for p in r.paginas):
        lineas.append("---")
        lineas.append("Las palabras marcadas con ==así== tienen baja confianza y conviene revisarlas.")
    escribir_atomico(destino, "\n".join(lineas) + "\n")
