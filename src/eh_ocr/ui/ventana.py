"""Ventana principal de eh-ocr."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, config, hardware
from ..documento import listar_archivos
from ..red import red_bloqueada
from .estilo import CLARA, OSCURA, qss
from .paginas import PaginaCola, PaginaInformes, PaginaInicio, etiqueta, tarjeta
from .revision import PaginaRevision
from .trabajador import Estado, Trabajador


def es_oscuro() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


class VentanaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("eh-ocr")
        self.resize(1280, 820)
        self.setMinimumSize(980, 640)
        self.paleta = OSCURA if es_oscuro() else CLARA
        self.setStyleSheet(qss(self.paleta))
        self.trabajador = Trabajador()
        self._sueltos = False

        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        lateral = QWidget()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(232)
        lv = QVBoxLayout(lateral)
        lv.setContentsMargins(12, 18, 12, 18)
        lv.setSpacing(4)
        marca = etiqueta("<b style='font-size:13pt'>eh-ocr</b>")
        lv.addWidget(marca)
        lv.addSpacing(10)

        self.paginas = QStackedWidget()
        self.inicio = PaginaInicio(self.trabajador)
        self.cola = PaginaCola(self.trabajador)
        self.revision = PaginaRevision(self.trabajador, self.paleta)
        self.informes = PaginaInformes(self.trabajador)
        for w in (self.inicio, self.cola, self.revision, self.informes):
            self.paginas.addWidget(w)

        self.grupo = QButtonGroup(self)
        self.botones = {}
        for clave, nombre, w in (
            ("inicio", "⤓  Procesar", self.inicio),
            ("cola", "☰  Lista", self.cola),
            ("revision", "⌕  Revisar", self.revision),
            ("informes", "▤  Informes", self.informes),
        ):
            b = QPushButton(nombre)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, c=clave: self.mostrar(c))
            self.grupo.addButton(b)
            self.botones[clave] = (b, w)
            lv.addWidget(b)
        lv.addStretch(1)

        estado = tarjeta()
        le = QVBoxLayout(estado)
        le.addWidget(etiqueta("<b>Estado del equipo</b>"))
        self.lbl_equipo = etiqueta("", "suave", envolver=True)
        self.lbl_equipo.setTextFormat(Qt.TextFormat.RichText)
        le.addWidget(self.lbl_equipo)
        lv.addWidget(estado)

        h.addWidget(lateral)
        h.addWidget(self.paginas, 1)

        self.inicio.archivos_elegidos.connect(self.agregar_archivos)
        self.cola.revisar.connect(self.abrir_revision)
        self.cola.marcar_para_revision.connect(self._marcar_sueltos)
        self.revision.volver.connect(lambda: self.mostrar("cola"))
        self.trabajador.cola_terminada.connect(self._cola_terminada)
        self.trabajador.pide_contrasenas.connect(self._pedir_contrasenas)

        self.mostrar("inicio")
        self._actualizar_equipo(cargando=True)
        QTimer.singleShot(200, self._cargar_motores)

    # --- navegación -----------------------------------------------------------
    def mostrar(self, clave: str) -> None:
        b, w = self.botones[clave]
        if clave == "revision" and self.revision.trabajo is None:
            terminados = [i for i, t in enumerate(self.trabajador.trabajos) if t.terminado]
            if terminados:
                self.revision.abrir(terminados[-1])
        if clave == "informes":
            self.informes.actualizar()
        b.setChecked(True)
        self.paginas.setCurrentWidget(w)

    def abrir_revision(self, indice: int) -> None:
        if self.revision.abrir(indice):
            self.mostrar("revision")

    # --- motores y estado -------------------------------------------------------
    def _cargar_motores(self) -> None:
        from ..pipeline import Motores

        Motores.obtener().rapid.disponible()  # carga los modelos una vez
        from ..tablas import ModelosTablas

        ModelosTablas.obtener().estado
        self._actualizar_equipo()

    def _actualizar_equipo(self, cargando: bool = False) -> None:
        from ..pipeline import Motores

        eq = hardware.detectar()
        m = Motores.obtener()
        if cargando:
            motores = "Cargando motores…"
        else:
            motores = (
                f"● RapidOCR ({m.rapid.modelos}): {'listo' if m.rapid.disponible() else 'no disponible'}<br>"
                f"● Tesseract: {'listo' if m.tesseract.disponible() else 'no disponible'}"
            )
        complemento = config.carpeta_complementos().exists() and any(config.carpeta_complementos().iterdir())
        if cargando:
            tablas_txt = "Tablas: cargando…"
        else:
            from ..tablas import ModelosTablas

            et = ModelosTablas.obtener().estado
            if et["layout_preciso"] and et["estructuras"] >= 2:
                tablas_txt = "Tablas: alta precisión"
            elif et["layout"]:
                tablas_txt = "Tablas: básica (faltan modelos precisos)"
            else:
                tablas_txt = "Tablas: solo con bordes"
        self.lbl_equipo.setText(
            f"● Sin internet: {'correcto' if red_bloqueada() else 'no verificado'}<br>"
            f"● Acelerador: {m.rapid.acelerador if not cargando else eq.acelerador}<br>"
            f"{motores}<br>"
            f"● {tablas_txt}<br>"
            f"● Manuscritos y fórmulas: {'instalado' if complemento else 'complemento no instalado'}<br>"
            f"<br>{eq.descripcion}<br>v{__version__}"
        )

    # --- cola ---------------------------------------------------------------------
    def agregar_archivos(self, rutas: list[Path]) -> None:
        """Agrega a la lista para elegir qué procesar. NO procesa todavía."""
        archivos = listar_archivos(rutas)
        if not archivos:
            return
        _, repetidos = self.trabajador.agregar(archivos)
        self.cola.sincronizar()
        self.mostrar("cola")
        if repetidos:
            self.statusBar().showMessage(
                f"{repetidos} archivo{'s' if repetidos != 1 else ''} ya estaba{'n' if repetidos != 1 else ''} en la lista.", 6000
            )

    def _marcar_sueltos(self, uno_solo: bool) -> None:
        self._sueltos = uno_solo

    def _cola_terminada(self) -> None:
        self.informes.actualizar()
        # Documento suelto: se abre la revisión automáticamente; en lotes, solo el informe.
        if self._sueltos:
            terminados = [i for i, t in enumerate(self.trabajador.trabajos) if t.terminado]
            if terminados:
                self.abrir_revision(terminados[-1])
        self._sueltos = False

    def _pedir_contrasenas(self, indices: list[int]) -> None:
        hubo = False
        for i in indices:
            t = self.trabajador.trabajos[i]
            for intento in range(3):
                etiqueta_txt = f"«{t.ruta.name}» está protegido.\nEscribe la contraseña (no se guarda):"
                if intento:
                    etiqueta_txt = "La contraseña no es correcta. Inténtalo de nuevo:"
                clave, ok = QInputDialog.getText(self, "PDF protegido", etiqueta_txt, QLineEdit.EchoMode.Password)
                if not ok or not clave:
                    break
                from ..documento import Documento, ErrorContrasena

                try:
                    Documento(t.ruta, clave).cerrar()
                except ErrorContrasena:
                    continue
                self.trabajador.reintentar_con_contrasena(i, clave)
                hubo = True
                break
            else:
                t.estado = Estado.ERROR
                t.mensaje = "Contraseña incorrecta"
                self.trabajador.trabajo_cambiado.emit(i)
        if hubo:
            QTimer.singleShot(100, self.trabajador.iniciar)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.trabajador.cancelar()
        super().closeEvent(e)
