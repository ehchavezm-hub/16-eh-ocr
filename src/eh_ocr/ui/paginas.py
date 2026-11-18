"""Pantallas Inicio, Cola y lotes, e Informes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import salidas
from ..documento import EXT_ADMITIDAS, EXT_HEIC
from ..modelo import EstadoPagina
from .trabajador import Estado, Trabajador


def tarjeta() -> QFrame:
    f = QFrame()
    f.setObjectName("tarjeta")
    return f


def etiqueta(texto: str, nombre: str | None = None, envolver: bool = False) -> QLabel:
    l = QLabel(texto)
    if nombre:
        l.setObjectName(nombre)
    l.setWordWrap(envolver)
    return l


def abrir_en_explorador(ruta: Path) -> bool:
    """Abre el Explorador de Windows; si `ruta` es un archivo, lo deja seleccionado."""
    ruta = Path(ruta)
    carpeta = ruta if ruta.is_dir() else ruta.parent
    try:
        if sys.platform == "win32":
            if ruta.is_file():
                # Explorer exige "/select," y la ruta en UN solo argumento
                subprocess.Popen(f'explorer /select,"{ruta}"')
            else:
                os.startfile(str(carpeta))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
        return True
    except OSError:
        return False


# --- Inicio -----------------------------------------------------------------

class ZonaArrastre(QFrame):
    archivos_soltados = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("zona")
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)
        icono = etiqueta("⬆", "zonaTitulo")
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icono.setStyleSheet("font-size: 28pt;")
        titulo = etiqueta("Arrastra aquí archivos o carpetas", "zonaTitulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = etiqueta("PDF · JPG · PNG · TIFF · BMP · WEBP — sin límite de páginas", "suave")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        botones = QHBoxLayout()
        botones.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_archivos = QPushButton("Elegir archivos")
        self.btn_archivos.setObjectName("primario")
        self.btn_carpeta = QPushButton("Elegir carpeta")
        botones.addWidget(self.btn_archivos)
        botones.addWidget(self.btn_carpeta)
        for w in (icono, titulo, sub):
            lay.addWidget(w)
        lay.addLayout(botones)
        self.btn_archivos.clicked.connect(self._elegir_archivos)
        self.btn_carpeta.clicked.connect(self._elegir_carpeta)

    def _marcar(self, activa: bool) -> None:
        self.setProperty("activa", activa)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._marcar(True)

    def dragLeaveEvent(self, e) -> None:  # noqa: N802
        self._marcar(False)

    def dropEvent(self, e) -> None:  # noqa: N802
        self._marcar(False)
        rutas = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        if rutas:
            self.archivos_soltados.emit(rutas)

    def _elegir_archivos(self) -> None:
        patrones = " ".join(f"*{e}" for e in sorted(EXT_ADMITIDAS | EXT_HEIC))
        rutas, _ = QFileDialog.getOpenFileNames(self, "Elegir documentos", "", f"Documentos ({patrones})")
        if rutas:
            self.archivos_soltados.emit([Path(r) for r in rutas])

    def _elegir_carpeta(self) -> None:
        ruta = QFileDialog.getExistingDirectory(self, "Elegir carpeta")
        if ruta:
            self.archivos_soltados.emit([Path(ruta)])


class PaginaInicio(QWidget):
    archivos_elegidos = Signal(list)

    def __init__(self, trabajador: Trabajador) -> None:
        super().__init__()
        self.trabajador = trabajador
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addWidget(etiqueta("Convertir documentos a texto", "titulo"))
        lay.addWidget(etiqueta("PDF, escaneos y fotos. Todo se procesa en este equipo, sin internet.", "subtitulo"))

        self.zona = ZonaArrastre()
        self.zona.archivos_soltados.connect(self.archivos_elegidos)
        lay.addWidget(self.zona, 1)

        fila = QHBoxLayout()
        fila.setSpacing(16)
        # Formatos
        t1 = tarjeta()
        l1 = QVBoxLayout(t1)
        l1.addWidget(etiqueta("<b>Formatos de salida</b>"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        self.checks: dict[str, QCheckBox] = {}
        for k, (clave, (nombre, _)) in enumerate(salidas.FORMATOS.items()):
            c = QCheckBox(nombre)
            c.setChecked(clave in salidas.FORMATOS_POR_DEFECTO)
            c.setMinimumWidth(c.sizeHint().width())  # nunca recortar el nombre
            c.toggled.connect(self._actualizar_formatos)
            self.checks[clave] = c
            grid.addWidget(c, k // 3, k % 3)
        grid.setColumnStretch(3, 1)
        l1.addLayout(grid)
        fila.addWidget(t1, 3)
        # Destino
        t2 = tarjeta()
        l2 = QVBoxLayout(t2)
        l2.addWidget(etiqueta("<b>Guardar en</b>"))
        destino = QHBoxLayout()
        self.lbl_destino = etiqueta("Junto al documento original", envolver=True)
        btn_cambiar = QPushButton("Cambiar…")
        btn_original = QPushButton("Junto al original")
        btn_cambiar.clicked.connect(self._cambiar_destino)
        btn_original.clicked.connect(self._destino_original)
        destino.addWidget(self.lbl_destino, 1)
        destino.addWidget(btn_cambiar)
        destino.addWidget(btn_original)
        l2.addLayout(destino)
        l2.addWidget(etiqueta("Idioma: detección automática (castellano · inglés · alemán)", "suave"))
        fila.addWidget(t2, 2)
        lay.addLayout(fila)

    def _actualizar_formatos(self) -> None:
        elegidos = tuple(k for k, c in self.checks.items() if c.isChecked())
        self.trabajador.formatos = elegidos or salidas.FORMATOS_POR_DEFECTO
        if not elegidos:
            self.checks["pdf"].setChecked(True)

    def _cambiar_destino(self) -> None:
        ruta = QFileDialog.getExistingDirectory(self, "Carpeta para los resultados")
        if ruta:
            self.trabajador.carpeta = Path(ruta)
            self.lbl_destino.setText(ruta)

    def _destino_original(self) -> None:
        self.trabajador.carpeta = None
        self.lbl_destino.setText("Junto al documento original")


# --- Cola y lotes -------------------------------------------------------------

COLUMNAS = ("", "Archivo", "Estado", "Páginas", "Confianza")


class PaginaCola(QWidget):
    revisar = Signal(int)

    def __init__(self, trabajador: Trabajador) -> None:
        super().__init__()
        self.trabajador = trabajador
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        cab = QHBoxLayout()
        textos = QVBoxLayout()
        self.lbl_titulo = etiqueta("Lista de documentos", "titulo")
        self.lbl_sub = etiqueta("Agrega documentos en «Procesar», marca los que quieras y pulsa «Procesar seleccionados».", "subtitulo")
        textos.addWidget(self.lbl_titulo)
        textos.addWidget(self.lbl_sub)
        cab.addLayout(textos, 1)
        self.btn_pausa = QPushButton("Pausar")
        self.btn_pausa.setCheckable(True)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("peligro")
        cab.addWidget(self.btn_pausa)
        cab.addWidget(self.btn_cancelar)
        lay.addLayout(cab)
        self.btn_pausa.toggled.connect(self._pausa)
        self.btn_cancelar.clicked.connect(self.trabajador.cancelar)

        t = tarjeta()
        lt = QVBoxLayout(t)
        fila = QHBoxLayout()
        self.lbl_progreso = etiqueta("<b>Progreso total</b>")
        fila.addWidget(self.lbl_progreso, 1)
        lt.addLayout(fila)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(10)
        lt.addWidget(self.barra)
        lay.addWidget(t)

        acciones = QHBoxLayout()
        self.btn_procesar = QPushButton("Procesar seleccionados")
        self.btn_procesar.setObjectName("primario")
        self.btn_todos = QPushButton("Marcar todos")
        self.btn_ninguno = QPushButton("Desmarcar todos")
        self.btn_quitar = QPushButton("Quitar de la lista")
        self.lbl_marcados = etiqueta("", "suave")
        for w in (self.btn_procesar, self.btn_todos, self.btn_ninguno, self.btn_quitar):
            acciones.addWidget(w)
        acciones.addWidget(self.lbl_marcados, 1)
        lay.addLayout(acciones)
        self.btn_procesar.clicked.connect(self._procesar)
        self.btn_todos.clicked.connect(lambda: self._marcar_todos(True))
        self.btn_ninguno.clicked.connect(lambda: self._marcar_todos(False))
        self.btn_quitar.clicked.connect(self._quitar)

        cuerpo = QSplitter()
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setShowGrid(False)
        self.tabla.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # se ve inicio y final del nombre
        self.tabla.setWordWrap(False)
        cab_t = self.tabla.horizontalHeader()
        cab_t.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cab_t.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cab_t.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cab_t.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        cab_t.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.cellDoubleClicked.connect(self._doble_clic)
        self.tabla.itemChanged.connect(self._casilla_cambiada)
        cuerpo.addWidget(self.tabla)

        lateral = tarjeta()
        ll = QVBoxLayout(lateral)
        ll.addWidget(etiqueta("<b>Ahora</b>"))
        self.lbl_ahora = etiqueta("—", envolver=True)
        self.lbl_ahora.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_ahora.setAlignment(Qt.AlignmentFlag.AlignTop)
        ll.addWidget(self.lbl_ahora, 1)
        self.btn_revisar = QPushButton("Revisar documento")
        self.btn_revisar.setObjectName("primario")
        self.btn_abrir = QPushButton("Abrir carpeta de resultados")
        ll.addWidget(self.btn_revisar)
        ll.addWidget(self.btn_abrir)
        self.btn_revisar.clicked.connect(self._revisar_seleccion)
        self.btn_abrir.clicked.connect(self._abrir_resultados)
        lateral.setMinimumWidth(240)
        lateral.setMaximumWidth(320)
        cuerpo.addWidget(lateral)
        cuerpo.setStretchFactor(0, 4)
        cuerpo.setStretchFactor(1, 1)
        lay.addWidget(cuerpo, 1)

        trabajador.trabajo_cambiado.connect(self.actualizar_fila)
        trabajador.progreso_total.connect(self._progreso)
        trabajador.cola_terminada.connect(self._terminada)

    # --- selección y procesamiento -----------------------------------------
    marcar_para_revision = Signal(bool)  # True si se procesa un solo archivo (abrir revisión al final)

    def _doble_clic(self, fila: int, _col: int) -> None:
        if self.trabajador.trabajos[fila].terminado:
            self.revisar.emit(fila)

    def _casilla_cambiada(self, item: QTableWidgetItem) -> None:
        if item.column() != 0 or item.row() >= len(self.trabajador.trabajos):
            return
        self.trabajador.trabajos[item.row()].marcado = item.checkState() == Qt.CheckState.Checked
        self._actualizar_botones()

    def _marcar_todos(self, valor: bool) -> None:
        for t in self.trabajador.trabajos:
            if t.estado != Estado.NO_ADMITIDO:
                t.marcado = valor
        self.sincronizar()

    def _procesar(self) -> None:
        n = len(self.trabajador.marcados_procesables())
        if n:
            self.marcar_para_revision.emit(n == 1)
            self.trabajador.procesar_marcados()
        self._actualizar_botones()

    def _quitar(self) -> None:
        filas = sorted({ix.row() for ix in self.tabla.selectionModel().selectedRows()})
        if not filas:  # sin filas seleccionadas: se quitan los desmarcados
            filas = [i for i, t in enumerate(self.trabajador.trabajos) if not t.marcado]
        self.trabajador.quitar(filas)
        self.sincronizar()

    def _actualizar_botones(self) -> None:
        n = len(self.trabajador.marcados_procesables())
        total = len(self.trabajador.trabajos)
        self.btn_procesar.setEnabled(n > 0)
        self.btn_procesar.setText(f"Procesar seleccionados ({n})" if n else "Procesar seleccionados")
        marcados = sum(1 for t in self.trabajador.trabajos if t.marcado)
        self.lbl_marcados.setText(f"{marcados} de {total} marcados" if total else "")

    def _pausa(self, pausado: bool) -> None:
        self.trabajador.pausar(pausado)
        self.btn_pausa.setText("Continuar" if pausado else "Pausar")

    def _seleccion(self) -> int | None:
        filas = self.tabla.selectionModel().selectedRows()
        return filas[0].row() if filas else None

    def _revisar_seleccion(self) -> None:
        i = self._seleccion()
        if i is None:
            terminados = [k for k, t in enumerate(self.trabajador.trabajos) if t.terminado]
            i = terminados[-1] if terminados else None
        if i is not None:
            self.revisar.emit(i)

    def _abrir_resultados(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from ..archivos import carpeta_salida

        i = self._seleccion()
        trabajos = self.trabajador.trabajos
        candidatos = [trabajos[i]] if i is not None else list(reversed(trabajos))
        for t in candidatos:
            existentes = [s for s in t.salidas if Path(s).exists()]
            if existentes:
                abrir_en_explorador(existentes[0])
                return
        if not candidatos:
            QMessageBox.information(self, "eh-ocr", "Todavía no hay documentos en la lista.")
            return
        # Aún sin resultados: se abre la carpeta donde se guardarán
        t = candidatos[0]
        destino = carpeta_salida(t.ruta, self.trabajador.carpeta)
        abrir_en_explorador(destino)
        QMessageBox.information(
            self,
            "eh-ocr",
            f"«{t.ruta.name}» todavía no tiene resultados ({t.estado.value.lower()}).\n"
            f"Se abrió la carpeta donde se guardarán:\n{destino}",
        )

    def sincronizar(self) -> None:
        self.tabla.setRowCount(len(self.trabajador.trabajos))
        for i in range(len(self.trabajador.trabajos)):
            self.actualizar_fila(i)
        n = len(self.trabajador.trabajos)
        self.lbl_titulo.setText(f"Lista: {n} archivo{'s' if n != 1 else ''}")
        self.lbl_sub.setText(
            "Marca los archivos y pulsa «Procesar seleccionados». Si cierras la ventana, "
            "al volver a procesar se retoma donde quedó."
        )
        self._actualizar_botones()

    def actualizar_fila(self, i: int) -> None:
        if i >= self.tabla.rowCount():
            self.tabla.setRowCount(len(self.trabajador.trabajos))
        t = self.trabajador.trabajos[i]
        estado = t.estado.value
        if t.estado == Estado.PROCESANDO and t.paginas:
            estado = f"● Página {t.pagina_actual} de {t.paginas}"
        elif t.mensaje and t.estado in (Estado.DUDOSO, Estado.ERROR, Estado.NO_ADMITIDO, Estado.CANCELADO):
            estado = f"{t.estado.value}: {t.mensaje}"
        prefijo = {Estado.LISTO: "✓ ", Estado.DUDOSO: "⚠ ", Estado.PROTEGIDO: "🔒 "}.get(t.estado, "")
        self.tabla.blockSignals(True)
        casilla = QTableWidgetItem()
        bloqueada = t.estado in (Estado.PROCESANDO, Estado.COLA, Estado.NO_ADMITIDO)
        casilla.setFlags(Qt.ItemFlag.ItemIsSelectable | (Qt.ItemFlag.NoItemFlags if bloqueada else Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable))
        casilla.setCheckState(Qt.CheckState.Checked if t.marcado else Qt.CheckState.Unchecked)
        casilla.setToolTip("Marcar para procesar")
        self.tabla.setItem(i, 0, casilla)
        valores = (
            t.ruta.name,
            prefijo + estado,
            str(t.paginas) if t.paginas else "—",
            f"{t.confianza * 100:.1f} %" if t.confianza is not None else "—",
        )
        for c, v in enumerate(valores, start=1):
            item = QTableWidgetItem(v)
            item.setToolTip(str(t.ruta) if c == 1 else v)
            self.tabla.setItem(i, c, item)
        self.tabla.blockSignals(False)
        if t.estado == Estado.PROCESANDO and t.detalle:
            d = t.detalle
            self.lbl_ahora.setText(
                f"<b>{t.ruta.name}</b><br>Página {d.get('pagina')} de {t.paginas}<br><br>"
                f"Tipo: {d.get('tipo', '—')}<br>"
                f"Preproceso: {d.get('pasos') or 'ninguno'}<br>"
                f"Motores: {' + '.join(d.get('motores', [])) or '—'}"
                f"{' (votación)' if len(d.get('motores', [])) > 1 else ''}<br>"
                f"Confianza: {d.get('confianza', 0) * 100:.1f} %<br>"
                f"Acelerador: {d.get('acelerador', 'CPU')}"
            )

    def _progreso(self, hechas: int, total: int) -> None:
        self.barra.setMaximum(max(total, 1))
        self.barra.setValue(hechas)
        self.lbl_progreso.setText(f"<b>Progreso total: {hechas} de {total} páginas</b>")

    def _terminada(self) -> None:
        self.btn_pausa.setChecked(False)
        self.lbl_ahora.setText("Procesamiento terminado.")
        self._actualizar_botones()


# --- Informes -------------------------------------------------------------------

class PaginaInformes(QWidget):
    def __init__(self, trabajador: Trabajador) -> None:
        super().__init__()
        self.trabajador = trabajador
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(etiqueta("Informes", "titulo"))
        lay.addWidget(etiqueta("Qué motor leyó cada página, con qué confianza y en cuánto tiempo.", "subtitulo"))
        self.texto = QTextBrowser()
        lay.addWidget(self.texto, 1)

    def actualizar(self) -> None:
        html = []
        for t in self.trabajador.trabajos:
            if t.resultado is None:
                if t.estado not in (Estado.COLA, Estado.PROCESANDO):
                    html.append(f"<h3>{t.ruta.name}</h3><p>{t.estado.value}. {t.mensaje}</p>")
                continue
            r = t.resultado
            html.append(f"<h3>{t.ruta.name}</h3>")
            html.append(
                f"<p>Confianza media: <b>{r.confianza_media * 100:.1f} %</b> · Tiempo: {r.segundos:.1f} s · "
                f"Páginas dudosas: {', '.join(map(str, r.paginas_dudosas)) or 'ninguna'} · "
                f"No procesadas: {', '.join(map(str, r.paginas_no_procesadas)) or 'ninguna'}</p>"
            )
            html.append("<table cellpadding='4'><tr><th align='left'>Pág.</th><th align='left'>Tipo</th>"
                        "<th align='left'>Motores</th><th align='left'>Confianza</th><th align='left'>Tablas</th><th align='left'>Dudosas</th>"
                        "<th align='left'>Tiempo</th></tr>")
            for p in r.paginas:
                estado = "no procesada: " + p.mensaje if p.estado == EstadoPagina.NO_PROCESADA else ""
                html.append(
                    f"<tr><td>{p.perfil.numero}</td><td>{p.perfil.tipo.value}</td>"
                    f"<td>{' + '.join(p.motores) or '—'}</td><td>{p.confianza_media * 100:.1f} %</td><td>{len(p.tablas)}</td>"
                    f"<td>{len(p.dudosas)} {estado}</td><td>{p.segundos:.1f} s</td></tr>"
                )
            html.append("</table>")
            if t.salidas:
                html.append("<p>Resultados: " + " · ".join(s.name for s in t.salidas) + "</p>")
        self.texto.setHtml("".join(html) or "<p>Aún no hay documentos procesados.</p>")
