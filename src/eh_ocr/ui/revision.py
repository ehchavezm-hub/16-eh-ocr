"""Pantalla de revisión: original y texto lado a lado, con las palabras dudosas resaltadas."""

from __future__ import annotations

import html
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGridLayout,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import pipeline, salidas
from ..documento import Documento
from ..modelo import EstadoPagina, Palabra, ResultadoPagina
from .estilo import Paleta, num, pct
from .paginas import abrir_en_explorador, etiqueta, tarjeta
from .trabajador import Estado, Trabajador

DPI_VISTA = 110


@dataclass
class Tramo:
    inicio: int
    fin: int
    palabra: Palabra


class VistaImagen(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._zoom = 1.0
        self._ajustar = True

    def ajustar(self) -> None:
        """Muestra la página completa (se repite al cambiar el tamaño de la ventana)."""
        self._ajustar = True
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def zoom(self, factor: float) -> None:
        self._ajustar = False
        self._zoom = max(0.05, min(8.0, self._zoom * factor))
        self.setTransform(self.transform().fromScale(self._zoom, self._zoom))

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if self._ajustar:
            self.ajustar()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self._ajustar:
            self.ajustar()

    def wheelEvent(self, e) -> None:  # noqa: N802
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
        else:
            super().wheelEvent(e)


class PaginaRevision(QWidget):
    volver = Signal()
    _reprocesada = Signal(int, object, str)  # número de página, ResultadoPagina | None, error

    def __init__(self, trabajador: Trabajador, paleta: Paleta) -> None:
        super().__init__()
        self.trabajador = trabajador
        self.paleta = paleta
        self.indice: int | None = None
        self.num_pagina = 0
        self.tramos: list[Tramo] = []
        self.rects: dict[int, QGraphicsRectItem] = {}
        self.actual: Palabra | None = None
        self._doc: Documento | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(10)

        # Barra en dos grupos: si la ventana es angosta, las acciones bajan a una segunda fila
        # (antes los botones se cortaban: «olver a la l…»).
        self.grupo_nav = QWidget()
        nav = QHBoxLayout(self.grupo_nav)
        nav.setContentsMargins(0, 0, 0, 0)
        btn_volver = QPushButton("← Lista")
        btn_volver.setToolTip("Volver a la lista de documentos (Ctrl+2)")
        btn_volver.clicked.connect(self.volver)
        self.btn_ant = QPushButton("‹")
        self.btn_ant.setAccessibleName("Página anterior")
        self.btn_ant.setToolTip("Página anterior (Ctrl+RePág)")
        self.btn_sig = QPushButton("›")
        self.btn_sig.setAccessibleName("Página siguiente")
        self.btn_sig.setToolTip("Página siguiente (Ctrl+AvPág)")
        self.lbl_pagina = etiqueta("Página — de —")
        btn_menos = QPushButton("−")
        btn_menos.setAccessibleName("Alejar")
        btn_menos.setToolTip("Alejar (Ctrl+−)")
        btn_mas = QPushButton("+")
        btn_mas.setAccessibleName("Acercar")
        btn_mas.setToolTip("Acercar (Ctrl++). También Ctrl + rueda del ratón")
        btn_ajustar = QPushButton("Ajustar")
        btn_ajustar.setToolTip("Ver la página completa (Ctrl+0)")
        for w in (btn_volver, self.btn_ant, self.lbl_pagina, self.btn_sig, btn_menos, btn_mas, btn_ajustar):
            nav.addWidget(w)
        for w in (self.btn_ant, self.btn_sig, btn_menos, btn_mas):
            w.setFixedWidth(40)

        self.grupo_acciones = QWidget()
        acc = QHBoxLayout(self.grupo_acciones)
        acc.setContentsMargins(0, 0, 0, 0)
        self.btn_reprocesar = QPushButton("Reprocesar página")
        self.btn_reprocesar.setToolTip("Vuelve a leer esta página en segundo plano")
        self.btn_dudosa = QPushButton("Siguiente dudosa")
        self.btn_dudosa.setObjectName("dudosa")
        self.btn_dudosa.setToolTip("Ir a la siguiente palabra dudosa (F3)")
        self.btn_guardar = QPushButton("Guardar resultados")
        self.btn_guardar.setObjectName("primario")
        self.btn_guardar.setToolTip("Guardar PDF, Word y los demás formatos con las correcciones (Ctrl+S)")
        for w in (self.btn_reprocesar, self.btn_dudosa, self.btn_guardar):
            acc.addWidget(w)

        self.barra = QGridLayout()
        self.barra.setContentsMargins(0, 0, 0, 0)
        self.barra.setHorizontalSpacing(12)
        self.barra.setVerticalSpacing(8)
        self._dos_filas: bool | None = None
        self._acomodar_barra(dos_filas=False)
        lay.addLayout(self.barra)

        self.btn_ant.clicked.connect(lambda: self.ir_a_pagina(self.num_pagina - 1))
        self.btn_sig.clicked.connect(lambda: self.ir_a_pagina(self.num_pagina + 1))
        btn_menos.clicked.connect(lambda: self.vista.zoom(1 / 1.2))
        btn_mas.clicked.connect(lambda: self.vista.zoom(1.2))
        btn_ajustar.clicked.connect(lambda: self.vista.ajustar())
        # Atajos: solo cuando esta pantalla está a la vista
        for tecla, accion in (
            ("F3", self.siguiente_dudosa),
            ("Ctrl+S", self.guardar),
            ("Ctrl+Return", self._aceptar),
            ("Ctrl+PgUp", lambda: self.ir_a_pagina(self.num_pagina - 1)),
            ("Ctrl+PgDown", lambda: self.ir_a_pagina(self.num_pagina + 1)),
            ("Ctrl++", lambda: self.vista.zoom(1.2)),
            ("Ctrl+=", lambda: self.vista.zoom(1.2)),
            ("Ctrl+-", lambda: self.vista.zoom(1 / 1.2)),
            ("Ctrl+0", lambda: self.vista.ajustar()),
        ):
            atajo = QShortcut(QKeySequence(tecla), self, activated=accion)
            atajo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.btn_dudosa.clicked.connect(self.siguiente_dudosa)
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_reprocesar.clicked.connect(self.reprocesar_pagina)
        self._reprocesada.connect(self._al_reprocesar)

        cuerpo = QSplitter()
        izq = tarjeta()
        li = QVBoxLayout(izq)
        li.setContentsMargins(12, 12, 12, 12)
        self.lbl_original = etiqueta("ORIGINAL", "seccion")
        li.addWidget(self.lbl_original)
        self.vista = VistaImagen()
        li.addWidget(self.vista, 1)
        cuerpo.addWidget(izq)

        der = tarjeta()
        ld = QVBoxLayout(der)
        ld.setContentsMargins(12, 12, 12, 12)
        ld.addWidget(etiqueta("TEXTO RECONOCIDO", "seccion"))
        ld.addWidget(etiqueta("Haz clic en cualquier palabra para corregirla. Las dudosas están en amarillo.", "suave", envolver=True))
        self.texto = QTextEdit()
        self.texto.setReadOnly(True)
        self.texto.cursorPositionChanged.connect(self._clic_en_texto)
        ld.addWidget(self.texto, 1)

        self.panel = QFrame()
        self.panel.setObjectName("tarjeta")
        lp = QVBoxLayout(self.panel)
        self.lbl_palabra = etiqueta("", envolver=True)
        self.lbl_palabra.setTextFormat(Qt.TextFormat.RichText)
        lp.addWidget(self.lbl_palabra)
        self.btn_aceptar = QPushButton("Está bien así")
        self.btn_aceptar.setObjectName("primario")
        self.btn_aceptar.setToolTip("Dejar la palabra como está y pasar a la siguiente dudosa (Ctrl+Enter)")
        self.editor = QLineEdit()
        self.editor.setPlaceholderText("Escribe la palabra correcta y pulsa Enter")
        self.editor.setMinimumWidth(160)
        self.btn_cambiar = QPushButton("Corregir")
        self.btn_cambiar.setToolTip("Guardar la palabra escrita y pasar a la siguiente dudosa (Enter)")
        fila = QHBoxLayout()  # escribir la corrección: el cuadro ocupa todo el ancho disponible
        fila.addWidget(self.editor, 1)
        fila.addWidget(self.btn_cambiar)
        lp.addLayout(fila)
        fila2 = QHBoxLayout()
        self.btn_aceptar_pagina = QPushButton("Aceptar toda la página")
        self.btn_aceptar_pagina.setToolTip("Dar por buenas todas las palabras dudosas de esta página")
        fila2.addWidget(self.btn_aceptar)
        fila2.addWidget(self.btn_aceptar_pagina)
        fila2.addStretch(1)
        lp.addLayout(fila2)
        self.btn_aceptar.clicked.connect(self._aceptar)
        self.btn_cambiar.clicked.connect(self._cambiar)
        self.editor.returnPressed.connect(self._cambiar)
        self.btn_aceptar_pagina.clicked.connect(self._aceptar_pagina)
        ld.addWidget(self.panel)  # siempre visible
        self._sin_seleccion()
        cuerpo.addWidget(der)
        cuerpo.setSizes([600, 600])
        lay.addWidget(cuerpo, 1)

        self.lbl_estado = etiqueta("", "suave", envolver=True)
        lay.addWidget(self.lbl_estado)

    # --- barra adaptable --------------------------------------------------------
    def _acomodar_barra(self, dos_filas: bool) -> None:
        if dos_filas == self._dos_filas:
            return
        self._dos_filas = dos_filas
        self.barra.removeWidget(self.grupo_nav)
        self.barra.removeWidget(self.grupo_acciones)
        self.barra.addWidget(self.grupo_nav, 0, 0, Qt.AlignmentFlag.AlignLeft)
        if dos_filas:
            self.barra.addWidget(self.grupo_acciones, 1, 0, Qt.AlignmentFlag.AlignRight)
        else:
            self.barra.addWidget(self.grupo_acciones, 0, 1, Qt.AlignmentFlag.AlignRight)

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        necesario = self.grupo_nav.sizeHint().width() + self.grupo_acciones.sizeHint().width() + 60
        self._acomodar_barra(self.width() < necesario)

    # --- carga ---------------------------------------------------------------
    def olvidar(self) -> None:
        """La lista cambió (se quitaron archivos): la revisión vuelve a empezar."""
        if self._doc is not None:
            self._doc.cerrar()
            self._doc = None
        self.indice = None
        self.vista.scene().clear()
        self.texto.clear()
        self.lbl_estado.setText("")
        self._sin_seleccion()

    @property
    def trabajo(self):
        return self.trabajador.trabajos[self.indice] if self.indice is not None else None

    def abrir(self, indice: int) -> bool:
        t = self.trabajador.trabajos[indice]
        if t.resultado is None:
            return False
        if self._doc is not None:
            self._doc.cerrar()
        self.indice = indice
        try:
            self._doc = Documento(t.ruta, t.contrasena)
        except Exception:
            self._doc = None
        dudosas = [p.perfil.numero for p in t.resultado.paginas if p.dudosas]
        self.ir_a_pagina(dudosas[0] if dudosas else 1)
        return True

    def _pagina(self) -> ResultadoPagina:
        return self.trabajo.resultado.paginas[self.num_pagina - 1]

    def ir_a_pagina(self, n: int) -> None:
        if self.trabajo is None or self.trabajo.resultado is None:
            return
        total = len(self.trabajo.resultado.paginas)
        if not 1 <= n <= total:
            return
        self.num_pagina = n
        self.lbl_pagina.setText(f"Página <b>{n}</b> de {total}")
        self.btn_ant.setEnabled(n > 1)
        self.btn_sig.setEnabled(n < total)
        self.actual = None
        self.vista._ajustar = True
        self._pintar_imagen()
        self._pintar_texto()
        self._actualizar_estado()
        dudosas = self._pagina().dudosas
        if dudosas:
            self._seleccionar(dudosas[0])  # lista para corregir, sin buscarla
        else:
            self._sin_seleccion()

    def _pintar_imagen(self) -> None:
        escena = self.vista.scene()
        escena.clear()
        self.rects.clear()
        r = self._pagina()
        if self._doc is None:
            escena.addText("No se pudo abrir el original.")
            return
        arr, dpi = self._doc.pagina(self.num_pagina - 1).imagen(DPI_VISTA)
        h, w = arr.shape[:2]
        qimg = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        escena.addItem(QGraphicsPixmapItem(QPixmap.fromImage(qimg)))
        escena.setSceneRect(QRectF(0, 0, w, h))
        if r.perfil.ancho_px:
            sx = w / r.perfil.ancho_px
            sy = h / r.perfil.alto_px
            color = QColor(self.paleta.dudosa_borde)
            relleno = QColor(self.paleta.dudosa)
            relleno.setAlpha(110)
            azul = QColor(self.paleta.acento)
            for t in r.tablas:
                x0, y0, x1, y1 = t.caja
                escena.addRect(QRectF(x0 * sx, y0 * sy, (x1 - x0) * sx, (y1 - y0) * sy), QPen(azul, 2, Qt.PenStyle.DashLine))
            for p in r.palabras:
                if not p.dudosa:
                    continue
                x0, y0, x1, y1 = p.caja
                item = escena.addRect(QRectF(x0 * sx, y0 * sy, (x1 - x0) * sx, (y1 - y0) * sy), QPen(color, 2), QBrush(relleno))
                self.rects[id(p)] = item
        self.lbl_original.setText(
            f"ORIGINAL ({r.perfil.tipo.value}"
            f"{f', enderezado {num(r.perfil.inclinacion)}°' if r.perfil.inclinacion else ''})"
        )
        if self.vista._ajustar:
            self.vista.ajustar()

    def _pintar_texto(self) -> None:
        r = self._pagina()
        self.texto.blockSignals(True)
        self.texto.clear()
        self.tramos = []
        cur = self.texto.textCursor()
        normal = QTextCharFormat()
        dudosa = QTextCharFormat()
        dudosa.setBackground(QColor(self.paleta.dudosa))
        dudosa.setFontWeight(600)
        corregida = QTextCharFormat()
        corregida.setFontUnderline(True)
        corregida.setUnderlineColor(QColor(self.paleta.acento))
        if r.estado == EstadoPagina.NO_PROCESADA:
            cur.insertText(f"[Página no procesada: {r.mensaje}. Usa «Reprocesar página».]", normal)
        for k, linea in enumerate(r.lineas):
            if k:
                cur.insertText("\n", normal)
            for i, p in enumerate(linea.palabras):
                if i:
                    cur.insertText(" ", normal)
                inicio = cur.position()
                fmt = dudosa if p.dudosa else (corregida if p.corregida_de else normal)
                cur.insertText(p.texto, fmt)
                self.tramos.append(Tramo(inicio, cur.position(), p))
        self.texto.moveCursor(QTextCursor.MoveOperation.Start)
        self.texto.blockSignals(False)

    def _actualizar_estado(self) -> None:
        r = self._pagina()
        total_dudosas = sum(len(p.dudosas) for p in self.trabajo.resultado.paginas)
        self.btn_dudosa.setText(f"Siguiente dudosa ({total_dudosas})" if total_dudosas else "Sin dudosas ✓")
        self.btn_dudosa.setEnabled(bool(total_dudosas))
        self.lbl_estado.setText(
            f"Página {r.perfil.numero}: {r.perfil.tipo.value} · Motores: {' + '.join(r.motores) or '—'}"
            f"{' (votación)' if len(r.motores) > 1 else ''} · Confianza media: {pct(r.confianza_media)} · "
            f"Tablas: {len(r.tablas)} · Idioma: {r.idioma or '—'} · Tiempo: {num(r.segundos)} s"
        )

    # --- corrección ----------------------------------------------------------
    def _clic_en_texto(self) -> None:
        pos = self.texto.textCursor().position()
        for t in self.tramos:
            if t.inicio <= pos <= t.fin:
                self._seleccionar(t.palabra)
                return

    def _sin_seleccion(self) -> None:
        self.actual = None
        self.lbl_palabra.setText(
            "<b>Corrección</b><br>Haz clic en una palabra del texto o pulsa «Siguiente dudosa»."
        )
        self.btn_aceptar.setText("Está bien así")
        for w in (self.btn_aceptar, self.btn_cambiar, self.editor):
            w.setEnabled(False)
        self.editor.clear()
        hay = (
            self.trabajo is not None
            and self.trabajo.resultado is not None
            and 1 <= self.num_pagina <= len(self.trabajo.resultado.paginas)
            and bool(self._pagina().dudosas)
        )
        self.btn_aceptar_pagina.setEnabled(hay)

    def _seleccionar(self, p: Palabra) -> None:
        self.actual = p
        for w in (self.btn_aceptar, self.btn_cambiar, self.editor):
            w.setEnabled(True)
        self.btn_aceptar_pagina.setEnabled(bool(self._pagina().dudosas))
        # Texto venido del documento: siempre escapado (un documento podría contener HTML)
        alternativas = "".join(
            f"<br>{html.escape(str(m))} leyó: <b>{html.escape(str(v))}</b>" for m, v in p.alternativas.items()
        )
        corregida = f"<br>Corregida automáticamente de: <b>{html.escape(p.corregida_de)}</b>" if p.corregida_de else ""
        estado = "Palabra dudosa" if p.dudosa else "Palabra"
        self.lbl_palabra.setText(
            f"<b>{estado} · confianza {pct(p.confianza, 0)}</b>{alternativas}{corregida}"
        )
        corta = p.texto if len(p.texto) <= 18 else p.texto[:17] + "…"
        self.btn_aceptar.setText(f"Está bien: «{corta}»")
        self.editor.setText(p.texto)
        self.editor.setFocus()
        self.editor.selectAll()
        item = self.rects.get(id(p))
        if item is not None:
            self.vista.centerOn(item)
            item.setPen(QPen(QColor(self.paleta.acento), 3))
        for t in self.tramos:
            if t.palabra is p:
                c = self.texto.textCursor()
                c.setPosition(t.inicio)
                c.setPosition(t.fin, QTextCursor.MoveMode.KeepAnchor)
                self.texto.blockSignals(True)
                self.texto.setTextCursor(c)
                self.texto.blockSignals(False)
                break

    def _resolver(self, texto: str) -> None:
        p = self.actual
        if p is None:
            return
        texto = texto.strip()
        if texto and texto != p.texto:
            if p.corregida_de is None:
                p.corregida_de = p.texto
            p.texto = texto
        p.dudosa = False
        p.confianza = max(p.confianza, 0.99)
        r = self._pagina()
        if r.estado == EstadoPagina.DUDOSA and not r.dudosas:
            r.estado = EstadoPagina.OK
        pipeline.guardar_cache(self.trabajo.ruta, r)
        self._pintar_imagen()
        self._pintar_texto()
        self._actualizar_estado()
        self._sin_seleccion()
        self.siguiente_dudosa()

    def _aceptar_pagina(self) -> None:
        r = self._pagina()
        for p in r.dudosas:
            p.dudosa = False
            p.confianza = max(p.confianza, 0.99)
        if r.estado == EstadoPagina.DUDOSA:
            r.estado = EstadoPagina.OK
        pipeline.guardar_cache(self.trabajo.ruta, r)
        self._pintar_imagen()
        self._pintar_texto()
        self._actualizar_estado()
        self._sin_seleccion()

    def _aceptar(self) -> None:
        if self.actual is not None:
            self._resolver(self.actual.texto)

    def _cambiar(self) -> None:
        self._resolver(self.editor.text())

    def siguiente_dudosa(self) -> None:
        if self.trabajo is None or self.trabajo.resultado is None:
            return
        paginas = self.trabajo.resultado.paginas
        orden = list(range(self.num_pagina - 1, len(paginas))) + list(range(0, self.num_pagina - 1))
        for k in orden:
            dudosas = paginas[k].dudosas
            if dudosas:
                if k + 1 != self.num_pagina:
                    self.ir_a_pagina(k + 1)
                self._seleccionar(dudosas[0])
                return

    def reprocesar_pagina(self) -> None:
        """Vuelve a leer la página en segundo plano: la ventana no se congela (puede tardar)."""
        t = self.trabajo
        if t is None or getattr(self, "_reprocesando", False):
            return
        self._reprocesando = True
        numero = self.num_pagina
        self.btn_reprocesar.setEnabled(False)
        self.btn_reprocesar.setText("Reprocesando…")
        self.lbl_estado.setText(f"Reprocesando la página {numero}… puedes seguir revisando otras páginas.")

        def trabajar() -> None:
            try:
                r = pipeline.procesar_documento(t.ruta, t.contrasena, paginas=[numero])
                self._reprocesada.emit(numero, r.paginas[numero - 1], "")
            except Exception as e:  # noqa: BLE001
                self._reprocesada.emit(numero, None, str(e))

        threading.Thread(target=trabajar, name="eh-ocr-reprocesar", daemon=True).start()

    def _al_reprocesar(self, numero: int, pagina, error: str) -> None:
        self._reprocesando = False
        self.btn_reprocesar.setEnabled(True)
        self.btn_reprocesar.setText("Reprocesar página")
        if error or pagina is None:
            QMessageBox.warning(self, "eh-ocr", f"No se pudo reprocesar la página {numero}: {error}")
            return
        self.trabajo.resultado.paginas[numero - 1] = pagina
        if numero == self.num_pagina:
            self.ir_a_pagina(numero)
        else:
            self._actualizar_estado()

    def guardar(self) -> None:
        t = self.trabajo
        if t is None or t.resultado is None:
            return
        try:
            t.salidas = salidas.generar(t.resultado, self.trabajador.formatos, self.trabajador.carpeta, t.contrasena)
        except Exception as e:
            QMessageBox.warning(self, "eh-ocr", f"No se pudieron guardar los resultados: {e}")
            return
        if not any(p.dudosas for p in t.resultado.paginas):
            t.estado = Estado.LISTO
            t.mensaje = ""
            self.trabajador.trabajo_cambiado.emit(self.indice)
        respuesta = QMessageBox.information(
            self,
            "eh-ocr",
            "Resultados guardados:\n" + "\n".join(Path(s).name for s in t.salidas),
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok,
        )
        if respuesta == QMessageBox.StandardButton.Open and t.salidas:
            abrir_en_explorador(t.salidas[0])
