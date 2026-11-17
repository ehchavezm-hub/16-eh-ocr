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


def test_lista_no_procesa_hasta_pulsar_y_no_repite(app, tmp_path):
    from eh_ocr.ui.trabajador import Estado
    from eh_ocr.ui.ventana import VentanaPrincipal

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    for ruta in (a, b):
        ruta.write_bytes(b"x")
    v = VentanaPrincipal()
    v.agregar_archivos([a, b])
    v.agregar_archivos([a])  # repetido
    tr = v.trabajador
    assert len(tr.trabajos) == 2
    assert all(t.estado == Estado.PENDIENTE for t in tr.trabajos)
    assert not tr.ocupado  # no empezó solo
    assert v.cola.tabla.columnCount() == 5
    # desmarcar uno y quitar los desmarcados
    tr.trabajos[1].marcado = False
    v.cola.sincronizar()
    assert v.cola.btn_procesar.text() == "Procesar seleccionados (1)"
    v.cola._quitar()
    assert [t.ruta.name for t in tr.trabajos] == ["a.png"]
    v.close()
