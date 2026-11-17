"""Votación entre motores y armado de líneas.

Dos motores leen la misma página. Las palabras se emparejan por línea y
por posición; donde coinciden la confianza sube, donde no coinciden
decide el diccionario y la confianza, y la palabra queda con las dos
lecturas como alternativas para la revisión.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from . import config
from .corrector import Diccionarios, diccionarios, normalizar
from .modelo import Linea, Palabra

PENALIZACION_DESACUERDO = 0.85
BONO_DICCIONARIO = 0.25


def agrupar_en_lineas(palabras: list[Palabra]) -> list[Linea]:
    """Agrupa palabras en líneas por solapamiento vertical y ordena la lectura."""
    if not palabras:
        return []
    restantes = sorted(palabras, key=lambda p: (p.cy, p.caja[0]))
    lineas: list[list[Palabra]] = []
    for p in restantes:
        colocada = False
        for linea in reversed(lineas[-6:]):
            y0 = min(w.caja[1] for w in linea)
            y1 = max(w.caja[3] for w in linea)
            alto = max(y1 - y0, 1)
            solape = min(y1, p.caja[3]) - max(y0, p.caja[1])
            if solape > 0.5 * min(alto, max(p.alto, 1)):
                linea.append(p)
                colocada = True
                break
        if not colocada:
            lineas.append([p])
    resultado = [Linea(sorted(l, key=lambda w: w.caja[0])) for l in lineas]
    resultado.sort(key=lambda l: (l.caja[1], l.caja[0]))
    return _separar_huecos(resultado)


def _separar_huecos(lineas: list[Linea]) -> list[Linea]:
    """Parte una línea si hay un hueco horizontal enorme (columnas, tablas simples)."""
    salida = []
    for l in lineas:
        actual = [l.palabras[0]]
        for prev, w in zip(l.palabras, l.palabras[1:]):
            alto = max(prev.alto, w.alto, 1)
            if w.caja[0] - prev.caja[2] > 6 * alto:
                salida.append(Linea(actual))
                actual = [w]
            else:
                actual.append(w)
        salida.append(Linea(actual))
    return salida


def _puntaje(p: Palabra, dic: Diccionarios) -> float:
    return p.confianza + (BONO_DICCIONARIO if dic.conoce(p.texto) else 0.0)


def _elegir(a: Palabra, b: Palabra, dic: Diccionarios) -> Palabra:
    ganadora = a if _puntaje(a, dic) >= _puntaje(b, dic) else b
    otra = b if ganadora is a else a
    final = Palabra(
        texto=ganadora.texto,
        confianza=ganadora.confianza * PENALIZACION_DESACUERDO,
        caja=a.caja,  # las cajas del motor principal son más precisas
        motor=ganadora.motor,
        alternativas={a.motor: a.texto, b.motor: b.texto},
    )
    # Si el diccionario da la razón a una sola lectura, la confianza mejora
    if dic.conoce(ganadora.texto) and not dic.conoce(otra.texto):
        final.confianza = max(final.confianza, 0.86)
    return final


def _dentro(p: Palabra, caja: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = caja
    margen = 0.3 * (y1 - y0)
    return x0 - margen <= p.cx <= x1 + margen and y0 - margen <= p.cy <= y1 + margen


def votar(principal: list[Palabra], secundaria: list[Palabra], dic: Diccionarios | None = None) -> list[Linea]:
    dic = dic or diccionarios()
    lineas_a = agrupar_en_lineas(principal)
    usadas: set[int] = set()
    salida: list[Linea] = []

    for linea in lineas_a:
        cand = [(i, p) for i, p in enumerate(secundaria) if i not in usadas and _dentro(p, linea.caja)]
        cand.sort(key=lambda t: t[1].caja[0])
        for i, _ in cand:
            usadas.add(i)
        b = [p for _, p in cand]
        a = linea.palabras
        if not b:
            for p in a:
                p.confianza *= 0.95  # sin confirmación del segundo motor
            salida.append(Linea(a))
            continue
        na = [normalizar(p.texto) for p in a]
        nb = [normalizar(p.texto) for p in b]
        resultado: list[Palabra] = []
        for op, i1, i2, j1, j2 in SequenceMatcher(None, na, nb, autojunk=False).get_opcodes():
            if op == "equal":
                for pa, pb in zip(a[i1:i2], b[j1:j2]):
                    pa.confianza = 1 - (1 - pa.confianza) * (1 - pb.confianza)
                    resultado.append(pa)
            elif op == "replace" and (i2 - i1) == (j2 - j1):
                for pa, pb in zip(a[i1:i2], b[j1:j2]):
                    resultado.append(_elegir(pa, pb, dic))
            elif op == "replace":
                seg_a, seg_b = a[i1:i2], b[j1:j2]
                prom_a = sum(_puntaje(p, dic) for p in seg_a) / len(seg_a)
                prom_b = sum(_puntaje(p, dic) for p in seg_b) / len(seg_b)
                elegido = seg_a if prom_a >= prom_b else seg_b
                texto_a = " ".join(p.texto for p in seg_a)
                texto_b = " ".join(p.texto for p in seg_b)
                for p in elegido:
                    p.confianza *= PENALIZACION_DESACUERDO
                    p.alternativas = {seg_a[0].motor: texto_a, seg_b[0].motor: texto_b}
                    resultado.append(p)
            elif op == "delete":  # solo lo leyó el motor principal
                for p in a[i1:i2]:
                    p.confianza *= 0.9
                    resultado.append(p)
            elif op == "insert":  # solo lo leyó el segundo motor
                for p in b[j1:j2]:
                    if p.confianza >= 0.92 and dic.conoce(p.texto):
                        p.confianza *= 0.9
                        resultado.append(p)
        resultado.sort(key=lambda p: p.caja[0])
        if resultado:
            salida.append(Linea(resultado))

    # Líneas que el motor principal no vio
    huerfanas = [p for i, p in enumerate(secundaria) if i not in usadas and p.confianza >= 0.6]
    for linea in agrupar_en_lineas(huerfanas):
        media = sum(p.confianza for p in linea.palabras) / len(linea.palabras)
        if media >= 0.85 and any(dic.conoce(p.texto) for p in linea.palabras):
            for p in linea.palabras:
                p.confianza *= 0.9
            salida.append(linea)

    salida.sort(key=lambda l: (l.caja[1], l.caja[0]))
    return salida


def marcar_dudosas(lineas: list[Linea], umbral: float = config.UMBRAL_PALABRA) -> None:
    dic = diccionarios()
    for l in lineas:
        for p in l.palabras:
            p.confianza = max(0.0, min(1.0, p.confianza))
            desacuerdo = len(set(p.alternativas.values())) > 1
            p.dudosa = p.confianza < umbral or (desacuerdo and not dic.conoce(p.texto))
