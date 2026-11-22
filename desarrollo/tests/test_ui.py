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


def test_panel_de_correccion_siempre_visible(app, escaneo):
    from eh_ocr.pipeline import procesar_documento
    from eh_ocr.ui.trabajador import Estado
    from eh_ocr.ui.ventana import VentanaPrincipal

    v = VentanaPrincipal()
    v.show()
    v.agregar_archivos([escaneo])
    t = v.trabajador.trabajos[0]
    t.resultado = procesar_documento(escaneo)
    pal = t.resultado.paginas[0].palabras[3]
    pal.dudosa = True  # forzar una dudosa
    t.estado = Estado.DUDOSO
    v.abrir_revision(0)  # como al terminar un documento
    rev = v.revision
    assert rev.panel.isVisible()
    assert rev.actual is pal  # la primera dudosa ya queda seleccionada
    rev.editor.setText("CORREGIDA")
    rev._cambiar()
    assert pal.texto == "CORREGIDA" and not pal.dudosa
    assert rev.panel.isVisible()
    v.close()


def test_informes_escapan_nombres_de_archivo(app, tmp_path):
    """Seguridad: un nombre de archivo con HTML no se interpreta en Informes."""
    from eh_ocr.ui.trabajador import Estado
    from eh_ocr.ui.ventana import VentanaPrincipal

    # Windows no admite < > en nombres de archivo: no hace falta crear el archivo para probarlo
    ruta = tmp_path / "<img src=x>contrato.pdf"
    v = VentanaPrincipal()
    v.trabajador.agregar([ruta])
    v.trabajador.trabajos[0].estado = Estado.ERROR
    v.trabajador.trabajos[0].mensaje = "<b>falla</b>"
    v.informes.actualizar()
    assert "<img" not in v.informes.texto.toHtml().split("<body")[1].replace("&lt;img", "")
    assert "&lt;img src=x&gt;contrato.pdf" in v.informes.texto.toHtml()
    v.close()


def test_reprocesar_no_congela_la_ventana(app, escaneo):
    from PySide6.QtCore import QEventLoop, QTimer

    from eh_ocr.pipeline import procesar_documento
    from eh_ocr.ui.trabajador import Estado
    from eh_ocr.ui.ventana import VentanaPrincipal

    v = VentanaPrincipal()
    v.agregar_archivos([escaneo])
    t = v.trabajador.trabajos[0]
    t.resultado = procesar_documento(escaneo)
    t.estado = Estado.LISTO
    v.abrir_revision(0)
    rev = v.revision
    rev.reprocesar_pagina()  # vuelve enseguida: trabaja en segundo plano
    assert rev.btn_reprocesar.text() == "Reprocesando…"
    import time

    limite = time.monotonic() + 180  # en CI cargado puede tardar varias veces lo normal (~15 s)
    while rev._reprocesando and time.monotonic() < limite:
        bucle = QEventLoop()
        QTimer.singleShot(100, bucle.quit)
        bucle.exec()
    assert rev.btn_reprocesar.text() == "Reprocesar página"
    assert "representantes" in rev._pagina().texto
    v.close()


def test_no_se_quita_mientras_se_procesa(app, tmp_path):
    import threading

    from eh_ocr.ui.ventana import VentanaPrincipal

    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    v = VentanaPrincipal()
    v.agregar_archivos([a])
    evento = threading.Event()
    v.trabajador._hilo = threading.Thread(target=evento.wait, daemon=True)  # simula proceso en curso
    v.trabajador._hilo.start()
    assert v.trabajador.quitar([0]) == 0 and len(v.trabajador.trabajos) == 1
    evento.set()
    v.trabajador._hilo.join()
    assert v.trabajador.quitar([0]) == 1 and v.trabajador.trabajos == []
    v.close()
