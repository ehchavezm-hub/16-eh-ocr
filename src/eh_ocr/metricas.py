"""Métricas de calidad: CER (error de caracteres) y WER (error de palabras)."""

from __future__ import annotations

import re
import unicodedata


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    return re.sub(r"\s+", " ", t).strip()


def _distancia(a: list, b: list) -> int:
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def cer(referencia: str, hipotesis: str) -> float:
    r, h = _normalizar(referencia), _normalizar(hipotesis)
    if not r:
        return 0.0 if not h else 1.0
    return _distancia(list(r), list(h)) / len(r)


def wer(referencia: str, hipotesis: str) -> float:
    r, h = _normalizar(referencia).split(), _normalizar(hipotesis).split()
    if not r:
        return 0.0 if not h else 1.0
    return _distancia(r, h) / len(r)
