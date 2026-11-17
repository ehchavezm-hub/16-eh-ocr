"""Salida Word (DOCX): texto y tablas reales (con celdas combinadas). Lo dudoso, en amarillo."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK, WD_COLOR_INDEX
from docx.shared import Pt

from ..archivos import escribir_atomico
from ..modelo import EstadoPagina, ResultadoDocumento
from ..tablas import Tabla


def _agregar_palabras(par, palabras) -> None:
    for i, w in enumerate(palabras):
        run = par.add_run(("" if i == 0 else " ") + w.texto)
        if w.dudosa:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _agregar_tabla(doc, t: Tabla, palabras) -> None:
    tabla = doc.add_table(rows=t.n_filas, cols=t.n_cols)
    tabla.style = "Table Grid"
    for c in t.celdas:
        f1 = min(c.fila + c.filas - 1, t.n_filas - 1)
        c1 = min(c.col + c.cols - 1, t.n_cols - 1)
        celda = tabla.cell(c.fila, c.col)
        if (f1, c1) != (c.fila, c.col):
            celda = celda.merge(tabla.cell(f1, c1))
        par = celda.paragraphs[0]
        _agregar_palabras(par, [palabras[i] for i in c.indices if i < len(palabras)])
    doc.add_paragraph()


def escribir(r: ResultadoDocumento, destino: Path) -> None:
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(11)
    estilo.paragraph_format.space_after = Pt(2)

    for k, p in enumerate(r.paginas):
        if k > 0:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        if p.estado == EstadoPagina.NO_PROCESADA:
            run = doc.add_paragraph().add_run(f"[Página {p.perfil.numero}: no procesada — {p.mensaje}]")
            run.italic = True
            continue
        palabras = p.palabras
        for tipo, bloque in p.bloques():
            if tipo == "tabla":
                _agregar_tabla(doc, bloque, palabras)
            else:
                _agregar_palabras(doc.add_paragraph(), bloque.palabras)

    if any(p.dudosas for p in r.paginas):
        nota = doc.add_paragraph().add_run(
            "Nota de eh-ocr: el texto resaltado en amarillo tiene baja confianza y conviene revisarlo."
        )
        nota.italic = True
        nota.font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    escribir_atomico(destino, buf.getvalue())
