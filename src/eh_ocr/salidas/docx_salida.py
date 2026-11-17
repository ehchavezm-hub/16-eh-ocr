"""Salida Word (DOCX). Las palabras dudosas se resaltan en amarillo."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK, WD_COLOR_INDEX
from docx.shared import Pt

from ..archivos import escribir_atomico
from ..modelo import EstadoPagina, ResultadoDocumento


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
            par = doc.add_paragraph()
            run = par.add_run(f"[Página {p.perfil.numero}: no procesada — {p.mensaje}]")
            run.italic = True
            continue
        for linea in p.lineas:
            par = doc.add_paragraph()
            for i, w in enumerate(linea.palabras):
                run = par.add_run(("" if i == 0 else " ") + w.texto)
                if w.dudosa:
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW

    if any(p.dudosas for p in r.paginas):
        par = doc.add_paragraph()
        nota = par.add_run("Nota de eh-ocr: el texto resaltado en amarillo tiene baja confianza y conviene revisarlo.")
        nota.italic = True
        nota.font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    escribir_atomico(destino, buf.getvalue())
