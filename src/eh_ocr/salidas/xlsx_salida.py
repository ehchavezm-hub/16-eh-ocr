"""Salida Excel (XLSX): una hoja por página.

- Páginas con tablas detectadas: el texto suelto va en la columna A y cada tabla con sus
  celdas reales (incluidas las combinadas) y bordes.
- Páginas sin tablas detectadas: filas = líneas, columnas por alineación del texto.
Los números se guardan como números para poder sumar en Excel. Lo dudoso, en amarillo.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..archivos import escribir_atomico, texto_xml
from ..modelo import EstadoPagina, Linea, Palabra, ResultadoDocumento, ResultadoPagina
from ..tablas import celda_dudosa, texto_celda

AMARILLO = PatternFill("solid", fgColor="FDE68A")
_LADO = Side(style="thin", color="808080")
BORDE = Border(left=_LADO, right=_LADO, top=_LADO, bottom=_LADO)
HUECO_COLUMNA = 2.0  # hueco horizontal (en alturas de letra) que separa dos celdas
_NUMERO = re.compile(r"^-?[\d.,]+$")


def _segmentos(linea: Linea) -> list[list[Palabra]]:
    segs = [[linea.palabras[0]]]
    for prev, w in zip(linea.palabras, linea.palabras[1:]):
        alto = max(prev.alto, w.alto, 1)
        if w.caja[0] - prev.caja[2] > HUECO_COLUMNA * alto:
            segs.append([w])
        else:
            segs[-1].append(w)
    return segs


def _columnas(segmentos: list[list[Palabra]], ancho_pagina: float) -> list[float]:
    """Posiciones x de inicio de columna, agrupando inicios de segmento cercanos."""
    tolerancia = max(ancho_pagina * 0.025, 10)
    inicios = sorted(s[0].caja[0] for s in segmentos)
    columnas: list[list[float]] = []
    for x in inicios:
        if columnas and x - columnas[-1][-1] <= tolerancia:
            columnas[-1].append(x)
        else:
            columnas.append([x])
    return [sum(c) / len(c) for c in columnas]


def _valor(texto: str):
    """Convierte números escritos a la peruana/española (1.234,56) o inglesa (1,234.56)."""
    texto = texto_xml(texto)
    t = texto.strip()
    if not _NUMERO.match(t) or not any(c.isdigit() for c in t):
        return t
    try:
        if "," in t and "." in t:
            t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
        elif "," in t:
            partes = t.split(",")
            t = t.replace(",", ".") if len(partes) == 2 and len(partes[1]) != 3 else t.replace(",", "")
        elif t.count(".") > 1:
            t = t.replace(".", "")
        return float(t) if "." in t else int(t)
    except ValueError:
        return texto


def _hoja_con_tablas(hoja, p: ResultadoPagina) -> None:
    palabras = p.palabras
    fila = 1
    anchos: dict[int, int] = {}
    for tipo, bloque in p.bloques():
        if tipo == "linea":
            celda = _poner(hoja, fila, 1, _valor(bloque.texto))
            if any(w.dudosa for w in bloque.palabras):
                celda.fill = AMARILLO
            fila += 1
            continue
        t = bloque
        for c in t.celdas:
            texto = texto_celda(c, palabras)
            r0, c0 = fila + c.fila, 1 + c.col
            r1, c1 = r0 + c.filas - 1, c0 + c.cols - 1
            celda = _poner(hoja, r0, c0, _valor(texto))
            celda.alignment = Alignment(vertical="top", wrap_text=True)
            if celda_dudosa(c, palabras):
                celda.fill = AMARILLO
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    hoja.cell(row=rr, column=cc).border = BORDE
            if (r1, c1) != (r0, c0):
                hoja.merge_cells(start_row=r0, start_column=c0, end_row=r1, end_column=c1)
            if c.cols == 1:
                anchos[c0] = max(anchos.get(c0, 0), min(len(texto), 50))
        fila += t.n_filas + 1  # una fila en blanco después de cada tabla
    for col, ancho in anchos.items():
        hoja.column_dimensions[get_column_letter(col)].width = min(max(ancho + 2, 8), 52)


def _hoja_por_alineacion(hoja, p: ResultadoPagina) -> None:
    filas = [_segmentos(l) for l in p.lineas]
    columnas = _columnas([s for f in filas for s in f], p.perfil.ancho_px or 2480)
    anchos: dict[int, int] = {}
    for i, segs in enumerate(filas, start=1):
        usadas: set[int] = set()
        for seg in segs:
            x = seg[0].caja[0]
            col = min(range(len(columnas)), key=lambda k: abs(columnas[k] - x)) + 1
            while col in usadas:  # dos segmentos en la misma columna: el siguiente libre
                col += 1
            usadas.add(col)
            texto = " ".join(w.texto for w in seg)
            celda = _poner(hoja, i, col, _valor(texto))
            celda.alignment = Alignment(vertical="top")
            if any(w.dudosa for w in seg):
                celda.fill = AMARILLO
            anchos[col] = max(anchos.get(col, 0), len(texto))
    for col, ancho in anchos.items():
        hoja.column_dimensions[get_column_letter(col)].width = min(max(ancho + 2, 8), 60)


def _poner(hoja, fila: int, col: int, valor):
    """Escribe una celda. Un texto que empieza con «=» queda como TEXTO, nunca como fórmula:
    el contenido de un documento no debe ejecutarse en Excel."""
    celda = hoja.cell(row=fila, column=col, value=valor)
    if isinstance(valor, str) and valor.startswith("="):
        celda.data_type = "s"
    return celda


def escribir(r: ResultadoDocumento, destino: Path) -> None:
    libro = Workbook()
    libro.remove(libro.active)
    for p in r.paginas:
        hoja = libro.create_sheet(f"Página {p.perfil.numero}")
        if p.estado == EstadoPagina.NO_PROCESADA or not p.lineas:
            hoja["A1"] = texto_xml(f"Página no procesada: {p.mensaje}") if p.mensaje else "Página sin texto"
            hoja["A1"].font = Font(italic=True)
        elif p.tablas:
            _hoja_con_tablas(hoja, p)
        else:
            _hoja_por_alineacion(hoja, p)
    if any(p.dudosas for p in r.paginas):
        nota = libro.create_sheet("Nota")
        nota["A1"] = "Las celdas en amarillo tienen palabras de baja confianza: conviene revisarlas."
    buf = io.BytesIO()
    libro.save(buf)
    escribir_atomico(destino, buf.getvalue())
