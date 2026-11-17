"""Pruebas de extremo a extremo del reconocimiento y las salidas (sin internet)."""

from __future__ import annotations

import json

import pdfplumber
import pikepdf
import pytest
from docx import Document as Docx

from eh_ocr import salidas
from eh_ocr.documento import Documento, ErrorContrasena, FormatoNoAdmitido
from eh_ocr.metricas import cer
from eh_ocr.modelo import TipoPagina
from eh_ocr.pipeline import procesar_documento
from eh_ocr.red import bloquear_red, desbloquear_red

from .conftest import TEXTO, TEXTO_EN, requiere_tesseract

META_CER_ESCANEO = 0.01  # < 1 % en escaneos limpios


@pytest.fixture(autouse=True)
def sin_red():
    bloquear_red()
    yield
    desbloquear_red()


def test_pdf_digital_exacto_sin_ocr(pdf_digital):
    r = procesar_documento(pdf_digital)
    p = r.paginas[0]
    assert p.perfil.tipo == TipoPagina.DIGITAL
    assert p.motores == ["PDF digital"]
    esperado = "\n".join(l.encode("latin-1", "replace").decode("latin-1") for l in TEXTO)
    assert cer(esperado, p.texto) == 0


@requiere_tesseract
def test_escaneo_inclinado_cumple_meta(escaneo):
    r = procesar_documento(escaneo)
    p = r.paginas[0]
    assert p.perfil.tipo == TipoPagina.ESCANEO
    assert abs(p.perfil.inclinacion) > 1.0  # se enderezó
    assert set(p.motores) == {"RapidOCR", "Tesseract"}  # votación
    assert cer("\n".join(TEXTO), p.texto) < META_CER_ESCANEO


@requiere_tesseract
def test_foto_de_celular_cumple_meta(foto):
    r = procesar_documento(foto)
    p = r.paginas[0]
    assert p.perfil.tipo == TipoPagina.FOTO
    assert "perspectiva corregida" in p.mensaje
    assert cer("\n".join(TEXTO), p.texto) < 0.05  # < 5 % en fotos


@requiere_tesseract
def test_pdf_escaneado_multipagina_y_salidas(pdf_escaneado, tmp_path):
    r = procesar_documento(pdf_escaneado)
    assert len(r.paginas) == 2
    assert cer("\n".join(TEXTO), r.paginas[0].texto) < META_CER_ESCANEO
    assert cer("\n".join(TEXTO_EN * 3), r.paginas[1].texto) < META_CER_ESCANEO

    rutas = salidas.generar(r, ("pdf", "docx", "txt", "md", "json"), tmp_path / "out")
    assert [p.suffix for p in rutas] == [".pdf", ".docx", ".txt", ".md", ".json"]

    with pdfplumber.open(rutas[0]) as pdf:
        texto_pdf = pdf.pages[0].extract_text()
    assert "Brücke" in texto_pdf and "representantes" in texto_pdf
    assert "ciudad de Lima" in texto_pdf  # los espacios entre palabras se conservan

    assert "proyecto." in "\n".join(par.text for par in Docx(rutas[1]).paragraphs)
    assert json.loads(rutas[4].read_text(encoding="utf-8"))["paginas"][1]["perfil"]["numero"] == 2

    # Volver a generar nunca sobrescribe
    rutas2 = salidas.generar(r, ("txt",), tmp_path / "out")
    assert rutas2[0].name == "escaneado_ocr (1).txt"


@requiere_tesseract
def test_reanudable_usa_cache(escaneo):
    r1 = procesar_documento(escaneo)
    r2 = procesar_documento(escaneo)
    assert r2.paginas[0].texto == r1.paginas[0].texto
    assert r2.segundos < r1.segundos


def test_pdf_con_contrasena(pdf_digital, tmp_path):
    protegido = tmp_path / "protegido.pdf"
    with pikepdf.open(pdf_digital) as pdf:
        pdf.save(protegido, encryption=pikepdf.Encryption(owner="dueño", user="clave123"))
    with pytest.raises(ErrorContrasena):
        Documento(protegido)
    with pytest.raises(ErrorContrasena) as e:
        Documento(protegido, "mala")
    assert e.value.incorrecta
    r = procesar_documento(protegido, contrasena="clave123")
    assert "representantes" in r.texto


def test_heic_no_admitido(tmp_path):
    ruta = tmp_path / "foto.heic"
    ruta.write_bytes(b"x")
    with pytest.raises(FormatoNoAdmitido, match="JPG"):
        Documento(ruta)
