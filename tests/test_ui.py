"""La ventana se abre sin errores (modo invisible)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_ventana_abre_y_navega(app):
    from eh_ocr.ui.ventana import VentanaPrincipal

    v = VentanaPrincipal()
    v.show()
    for clave in ("cola", "revision", "informes", "inicio"):
        v.mostrar(clave)
    assert v.windowTitle() == "eh-ocr"
    assert v.inicio.checks["pdf"].isChecked() and v.inicio.checks["docx"].isChecked()
    v.close()
