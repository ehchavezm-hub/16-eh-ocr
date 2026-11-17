"""Diccionarios (castellano, inglés, alemán) y corrección de confusiones típicas de OCR.

La corrección es conservadora: solo cambia una palabra si NO existe en
ningún diccionario y una variante por confusión típica (rn↔m, 0↔o, 1↔l…)
SÍ existe. Nunca hace corrección ortográfica libre (cambiaría nombres
propios). Cada cambio queda marcado en la palabra.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from functools import lru_cache

from .modelo import Palabra

_PUNTUACION = "\"'“”‘’«»()[]{}¿?¡!.,;:…–—-/\\*"

# (de, a): pares de confusión frecuentes en OCR
CONFUSIONES = [
    ("rn", "m"), ("m", "rn"), ("cl", "d"), ("d", "cl"), ("vv", "w"), ("w", "vv"),
    ("ii", "ü"), ("li", "h"), ("0", "o"), ("o", "0"), ("1", "l"), ("l", "1"),
    ("1", "i"), ("I", "l"), ("l", "I"), ("5", "s"), ("8", "B"), ("6", "b"),
    ("ä", "a"), ("a", "ä"), ("o", "ö"), ("u", "ü"), ("n", "ñ"), ("e", "é"),
    ("a", "á"), ("i", "í"), ("o", "ó"), ("u", "ú"), ("c", "e"), ("e", "c"),
]

_DIGITOS_A_LETRAS = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"})


def separar_puntuacion(texto: str) -> tuple[str, str, str]:
    i, j = 0, len(texto)
    while i < j and texto[i] in _PUNTUACION:
        i += 1
    while j > i and texto[j - 1] in _PUNTUACION:
        j -= 1
    return texto[:i], texto[i:j], texto[j:]


def normalizar(texto: str) -> str:
    """Forma comparable: minúsculas, sin puntuación de borde, NFC."""
    _, nucleo, _ = separar_puntuacion(texto)
    return unicodedata.normalize("NFC", nucleo).lower()


class Diccionarios:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listas: dict[str, object] = {}

    def _lista(self, idioma: str):
        with self._lock:
            if idioma not in self._listas:
                from spellchecker import SpellChecker

                self._listas[idioma] = SpellChecker(language=idioma, distance=1)
            return self._listas[idioma]

    def idiomas_que_conocen(self, palabra: str) -> list[str]:
        p = normalizar(palabra)
        if not p:
            return []
        return [i for i in ("es", "en", "de") if p in self._lista(i)]

    def conoce(self, palabra: str) -> bool:
        p = normalizar(palabra)
        if not p:
            return True
        if _es_numero(p):
            return True
        return any(p in self._lista(i) for i in ("es", "en", "de"))

    def detectar_idioma(self, palabras: list[str]) -> str:
        votos = {"es": 0, "en": 0, "de": 0}
        for w in palabras[:400]:
            p = normalizar(w)
            if len(p) < 3:
                continue
            for i in votos:
                if p in self._lista(i):
                    votos[i] += 1
        mejor = max(votos, key=votos.get)
        return mejor if votos[mejor] > 0 else ""


@lru_cache(maxsize=1)
def diccionarios() -> Diccionarios:
    return Diccionarios()


def _es_numero(p: str) -> bool:
    return bool(re.fullmatch(r"[\d.,:/%$€+\-°ºª]+", p))


def _candidatos(nucleo: str):
    vistos = set()
    for de, a in CONFUSIONES:
        inicio = 0
        while True:
            k = nucleo.find(de, inicio)
            if k < 0:
                break
            c = nucleo[:k] + a + nucleo[k + len(de):]
            if c not in vistos:
                vistos.add(c)
                yield c
            inicio = k + 1


def corregir_palabra(palabra: Palabra, dic: Diccionarios | None = None) -> bool:
    """Corrige en el lugar si encuentra una variante válida. Devuelve True si cambió."""
    dic = dic or diccionarios()
    pre, nucleo, post = separar_puntuacion(palabra.texto)
    if len(nucleo) < 2:
        return False
    # Números con letras confundidas: "2O26" -> "2026"
    if sum(c.isdigit() for c in nucleo) >= max(2, len(nucleo) - 2) and not nucleo.isdigit():
        candidato = nucleo.translate(_DIGITOS_A_LETRAS)
        if candidato != nucleo and _es_numero(candidato):
            palabra.corregida_de = palabra.texto
            palabra.texto = pre + candidato + post
            return True
        return False
    if dic.conoce(nucleo):
        return False
    for c in _candidatos(nucleo):
        if dic.conoce(c):
            if nucleo[:1].isupper() and c[:1].islower():
                c = c[:1].upper() + c[1:]
            palabra.corregida_de = palabra.texto
            palabra.texto = pre + c + post
            return True
    return False
