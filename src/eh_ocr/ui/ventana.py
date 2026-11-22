"""Ventana principal de eh-ocr."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QInputDialog,
    QLabel,
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
from .estilo import CLARA, icono, qss
from .paginas import PaginaCola, PaginaInformes, PaginaInicio, etiqueta, tarjeta
from .revision import PaginaRevision
from .trabajador import Estado, Trabajador


def forzar_tema_claro() -> None:
    """eh-ocr se ve SIEMPRE en claro (decisión del usuario), aunque Windows esté en modo oscuro:
    ventana, mensajes, menús, avisos y barras de desplazamiento."""
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)  # Qt 6.8 o superior
    except Exception:  # noqa: BLE001
        pass
    # El estilo de Windows 11 en modo oscuro ignora la paleta: Fusion la respeta siempre.
    app.setStyle("Fusion")
    p = CLARA
    paleta = QPalette()
    for rol, color in (
        (QPalette.ColorRole.Window, p.fondo), (QPalette.ColorRole.WindowText, p.texto),
        (QPalette.ColorRole.Base, p.panel), (QPalette.ColorRole.AlternateBase, p.lateral),
        (QPalette.ColorRole.Text, p.texto), (QPalette.ColorRole.Button, p.panel),
        (QPalette.ColorRole.ButtonText, p.texto), (QPalette.ColorRole.Highlight, p.acento),
        (QPalette.ColorRole.HighlightedText, p.acento_texto), (QPalette.ColorRole.ToolTipBase, p.panel),
        (QPalette.ColorRole.ToolTipText, p.texto), (QPalette.ColorRole.PlaceholderText, p.texto_suave),
        (QPalette.ColorRole.Link, p.acento),
    ):
        paleta.setColor(rol, QColor(color))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(p.texto_suave))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(p.texto_suave))
    app.setPalette(paleta)
    # Mensajes y diálogos (QMessageBox, contraseña) son ventanas aparte: también con la hoja clara.
    app.setStyleSheet(qss(p))


class VentanaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("eh-ocr")
        self.resize(1280, 820)
        self.setMinimumSize(980, 640)
        forzar_tema_claro()
        self.paleta = CLARA
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
        cabecera = QHBoxLayout()
        cabecera.setContentsMargins(6, 0, 0, 0)
        cabecera.setSpacing(10)
        logo = QLabel("eh")
        logo.setObjectName("logo")
        logo.setFixedSize(26, 26)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cabecera.addWidget(logo)
        cabecera.addWidget(etiqueta("eh-ocr", "marca"), 1)
        lv.addLayout(cabecera)
        lv.addSpacing(18)

        self.paginas = QStackedWidget()
        self.inicio = PaginaInicio(self.trabajador, self.paleta)
        self.cola = PaginaCola(self.trabajador, self.paleta)
        self.revision = PaginaRevision(self.trabajador, self.paleta)
        self.informes = PaginaInformes(self.trabajador, self.paleta)
        for w in (self.inicio, self.cola, self.revision, self.informes):
            self.paginas.addWidget(w)

        self.grupo = QButtonGroup(self)
        self.botones = {}
        for k, (clave, nombre, ic, w) in enumerate((
            ("inicio", "Procesar", "procesar", self.inicio),
            ("cola", "Lista", "lista", self.cola),
            ("revision", "Revisar", "revisar", self.revision),
            ("informes", "Informes", "informes", self.informes),
        ), start=1):
            b = QPushButton("  " + nombre)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(icono(ic, self.paleta))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(f"{nombre} (Ctrl+{k})")
            b.clicked.connect(lambda _=False, c=clave: self.mostrar(c))
            QShortcut(QKeySequence(f"Ctrl+{k}"), self, activated=lambda c=clave: self.mostrar(c))
            self.grupo.addButton(b)
            self.botones[clave] = (b, w)
            lv.addWidget(b)
        lv.addStretch(1)

        estado = tarjeta()
        le = QVBoxLayout(estado)
        le.setContentsMargins(12, 12, 12, 12)
        le.setSpacing(6)
        le.addWidget(etiqueta("ESTADO DEL EQUIPO", "seccion"))
        self.lbl_equipo = etiqueta("", "suave", envolver=True)
        self.lbl_equipo.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_equipo.setToolTip(
            "Verde: listo. Naranja: funciona, con menos precisión.\n"
            "«Básico» = faltan los modelos precisos: instálalos con instalar.py y el paquete de eh-ocr."
        )
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
        self.trabajador.lista_cambiada.connect(self.revision.olvidar)

        # El recuadro de foco solo aparece al moverse con Tab, no después de cada clic.
        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
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

        p = self.paleta
        eq = hardware.detectar()
        m = Motores.obtener()
        filas: list[tuple[str, str]] = []  # (color del punto, texto)

        def fila(color: str, texto: str) -> None:
            filas.append((color, texto))

        if red_bloqueada():
            fila(p.ok, "Sin internet: correcto")
        else:
            fila(p.aviso, "Sin internet: no verificado")
        solo_cpu = (config.carpeta_datos() / "solo_cpu").exists()
        acelerador = eq.acelerador if cargando else m.rapid.acelerador
        if solo_cpu:
            fila(p.aviso, f"Acelerador: {acelerador} (la gráfica falló antes; se usa el procesador)")
        else:
            fila(p.ok, f"Acelerador: {acelerador}")
        if cargando:
            fila(p.texto_suave, "Cargando motores…")
            fila(p.texto_suave, "Tablas: cargando…")
        else:
            rapid = m.rapid.disponible()
            preciso = m.rapid.modelos == "medium"
            fila(p.ok if rapid and preciso else (p.aviso if rapid else p.error),
                 f"RapidOCR: {'listo' if rapid else 'no disponible'}{'' if preciso or not rapid else ', básico'}")
            tess = m.tesseract.disponible()
            fila(p.ok if tess else p.aviso, f"Tesseract: {'listo' if tess else 'no disponible'}")
            from ..tablas import ModelosTablas

            et = ModelosTablas.obtener().estado
            if et["layout_preciso"] and et["estructuras"] >= 2:
                fila(p.ok, "Tablas: alta precisión")
            elif et["layout"]:
                fila(p.aviso, "Tablas: básica")
            else:
                fila(p.aviso, "Tablas: solo con bordes")
        complemento = config.carpeta_complementos().exists() and any(config.carpeta_complementos().iterdir())
        fila(p.ok if complemento else p.texto_suave,
             f"Manuscritos: {'instalado' if complemento else 'no instalado'}")
        lineas = "".join(
            f"<tr><td valign='top' style='color:{color}; padding-right:6px'>●</td><td>{texto}</td></tr>"
            for color, texto in filas
        )
        self.lbl_equipo.setText(
            f"<table cellspacing='0' cellpadding='1'>{lineas}</table>"
            f"<p style='margin-top:8px'>{eq.descripcion}<br>versión {__version__}</p>"
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
