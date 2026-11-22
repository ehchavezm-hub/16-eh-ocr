"""Reglas técnicas: escritura atómica, nombres únicos, red bloqueada, métricas, corrector."""

from __future__ import annotations

import socket

import pytest

from eh_ocr.archivos import carpeta_salida, escribir_atomico, ruta_unica
from eh_ocr.corrector import corregir_palabra
from eh_ocr.metricas import cer, wer
from eh_ocr.modelo import Palabra
from eh_ocr.red import RedBloqueadaError, bloquear_red, desbloquear_red


def test_escritura_atomica_y_sin_temporales(tmp_path):
    destino = tmp_path / "a" / "salida.txt"
    escribir_atomico(destino, "hola ñandú")
    assert destino.read_text(encoding="utf-8") == "hola ñandú"
    assert [p.name for p in destino.parent.iterdir()] == ["salida.txt"]


def test_nunca_sobrescribe(tmp_path):
    (tmp_path / "informe.txt").write_text("x")
    (tmp_path / "informe (1).txt").write_text("x")
    assert ruta_unica(tmp_path, "informe", ".txt").name == "informe (2).txt"


def test_carpeta_salida_junto_al_original(tmp_path):
    origen = tmp_path / "doc.pdf"
    origen.write_bytes(b"")
    assert carpeta_salida(origen) == tmp_path


def test_red_bloqueada():
    bloquear_red()
    try:
        with pytest.raises(RedBloqueadaError):
            socket.create_connection(("example.com", 443), timeout=1)
        with pytest.raises(RedBloqueadaError):
            socket.getaddrinfo("example.com", 443)
    finally:
        desbloquear_red()


def test_metricas():
    assert cer("hola", "hola") == 0
    assert cer("hola", "hoia") == pytest.approx(0.25)
    assert wer("uno dos tres", "uno dos") == pytest.approx(1 / 3)


@pytest.mark.parametrize(
    "leido,esperado",
    [("rnodelo", "modelo"), ("Brücke", "Brücke"), ("2O26", "2026"), ("cuaderno", "cuaderno")],
)
def test_corrector_confusiones(leido, esperado):
    p = Palabra(leido, 0.7, (0, 0, 1, 1))
    corregir_palabra(p)
    assert p.texto == esperado
    if leido != esperado:
        assert p.corregida_de == leido
