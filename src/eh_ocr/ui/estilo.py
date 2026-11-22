"""Colores, íconos y hoja de estilo. La app usa SIEMPRE la paleta clara (OSCURA queda de reserva).

Los íconos se dibujan con QPainter: no dependen de archivos ni de complementos de imagen,
así que se ven igual en Python y en el .exe.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paleta:
    fondo: str
    panel: str
    lateral: str
    borde: str
    texto: str
    texto_suave: str
    acento: str
    acento_texto: str
    acento_suave: str
    zona: str
    zona_borde: str
    dudosa: str
    dudosa_borde: str
    ok: str
    aviso: str
    error: str


CLARA = Paleta(
    fondo="#e8ebf0", panel="#ffffff", lateral="#f6f7f9", borde="#d6dae1",
    texto="#1f2937", texto_suave="#4b5563", acento="#1d4ed8", acento_texto="#ffffff",
    acento_suave="#dbe6fb", zona="#f5f8fe", zona_borde="#8aa6db",
    dudosa="#fde68a", dudosa_borde="#d97706", ok="#166534", aviso="#92400e", error="#9a3412",
)

OSCURA = Paleta(
    fondo="#16181d", panel="#1f2229", lateral="#1a1d23", borde="#343944",
    texto="#e5e7eb", texto_suave="#a7afbd", acento="#5b8def", acento_texto="#0b1020",
    acento_suave="#24324f", zona="#1c2333", zona_borde="#4a6aa8",
    dudosa="#6b5410", dudosa_borde="#f0b429", ok="#6ee7a0", aviso="#fbbf24", error="#fb923c",
)


def num(valor: float, decimales: int = 1) -> str:
    """Número con coma decimal, como se escribe en castellano: 99,7."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def pct(fraccion: float, decimales: int = 1) -> str:
    return f"{num(fraccion * 100, decimales)} %"


# --- íconos -----------------------------------------------------------------------
_TRAZOS = {
    # Trazos en una rejilla de 24×24, como los íconos de línea habituales.
    "procesar": [("linea", (12, 4, 12, 15)), ("poli", ((7, 10), (12, 15), (17, 10))), ("poli", ((4, 16), (4, 20), (20, 20), (20, 16)))],
    "lista": [("linea", (8, 6, 20, 6)), ("linea", (8, 12, 20, 12)), ("linea", (8, 18, 20, 18)),
              ("punto", (4, 6)), ("punto", (4, 12)), ("punto", (4, 18))],
    "revisar": [("circulo", (10.5, 10.5, 6)), ("linea", (15, 15, 20, 20))],
    "informes": [("poli", ((6, 3), (14, 3), (19, 8), (19, 21), (6, 21), (6, 3))), ("poli", ((14, 3), (14, 8), (19, 8))),
                 ("linea", (9, 13, 16, 13)), ("linea", (9, 17, 16, 17))],
    "subir": [("linea", (12, 15, 12, 4)), ("poli", ((7, 9), (12, 4), (17, 9))), ("poli", ((4, 15), (4, 20), (20, 20), (20, 15)))],
}


def pixmap_icono(nombre: str, color: str, tam: int = 18, grosor: float = 2.0):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap, QPolygonF

    escala = 2.0
    app = QGuiApplication.instance()
    if app is not None and app.primaryScreen() is not None:
        escala = max(1.0, app.primaryScreen().devicePixelRatio())
    pm = QPixmap(int(tam * escala), int(tam * escala))
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(escala)
    pintor = QPainter(pm)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = tam / 24
    pluma = QPen(QColor(color), grosor * max(k, 0.75))
    pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
    pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pintor.setPen(pluma)
    for tipo, d in _TRAZOS[nombre]:
        if tipo == "linea":
            pintor.drawLine(QPointF(d[0] * k, d[1] * k), QPointF(d[2] * k, d[3] * k))
        elif tipo == "poli":
            pintor.drawPolyline(QPolygonF([QPointF(x * k, y * k) for x, y in d]))
        elif tipo == "circulo":
            pintor.drawEllipse(QPointF(d[0] * k, d[1] * k), d[2] * k, d[2] * k)
        elif tipo == "punto":
            pintor.setBrush(QColor(color))
            pintor.drawEllipse(QPointF(d[0] * k, d[1] * k), 1.2 * k, 1.2 * k)
            pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.end()
    return pm


def icono(nombre: str, p: "Paleta", tam: int = 18):
    """Ícono gris; azul cuando el botón está marcado (navegación)."""
    from PySide6.QtGui import QIcon

    ic = QIcon()
    ic.addPixmap(pixmap_icono(nombre, p.texto_suave, tam), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap_icono(nombre, p.acento, tam), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(pixmap_icono(nombre, p.texto_suave, tam), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def _marca_casilla(p: "Paleta") -> str:
    """PNG de la marca ✓ de las casillas (Qt la pierde al dar estilo propio a la casilla)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

    carpeta = Path(tempfile.gettempdir()) / "eh-ocr-ui"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"marca-{p.acento_texto.lstrip('#')}.png"
    if not ruta.exists():
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(pm)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pluma = QPen(QColor(p.acento_texto), 4.2)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pintor.setPen(pluma)
        pintor.drawPolyline(QPolygonF([QPointF(8, 16.5), QPointF(13.5, 22), QPointF(24, 10)]))
        pintor.end()
        tmp = ruta.with_suffix(".tmp.png")
        pm.save(str(tmp), "PNG")
        tmp.replace(ruta)
    return ruta.as_posix()


def qss(p: Paleta) -> str:
    try:
        marca = _marca_casilla(p)
    except Exception:  # noqa: BLE001 — sin la imagen, la casilla marcada se ve rellena de azul
        marca = ""
    return f"""
    QWidget {{ color: {p.texto}; font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }}
    QMainWindow, #raiz {{ background: {p.fondo}; }}
    #lateral {{ background: {p.lateral}; border-right: 1px solid {p.borde}; }}
    #tarjeta {{ background: {p.panel}; border: 1px solid {p.borde}; border-radius: 10px; }}
    #zona {{ background: {p.zona}; border: 2px dashed {p.zona_borde}; border-radius: 14px; }}
    #zona[activa="true"] {{ background: {p.acento_suave}; border-color: {p.acento}; }}
    #titulo {{ font-size: 18pt; font-weight: 700; }}
    #subtitulo, #suave {{ color: {p.texto_suave}; }}
    #zonaTitulo {{ font-size: 14pt; font-weight: 600; }}
    QPushButton {{
        min-height: 36px; padding: 0 16px; border-radius: 8px;
        border: 1px solid {p.borde}; background: {p.panel}; font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {p.acento}; }}
    QPushButton:disabled {{ color: {p.texto_suave}; }}
    QPushButton#primario {{ background: {p.acento}; color: {p.acento_texto}; border: none; }}
    QPushButton#peligro {{ color: {p.error}; border-color: {p.error}; }}
    QPushButton#dudosa {{ background: {p.dudosa}; border-color: {p.dudosa_borde}; }}
    QPushButton#nav {{
        text-align: left; border: none; background: transparent; padding: 0 12px;
        min-height: 40px; font-weight: 500;
    }}
    QPushButton#nav:checked {{ background: {p.acento_suave}; color: {p.acento}; font-weight: 700; }}
    QProgressBar {{ border: none; border-radius: 5px; background: {p.borde}; height: 10px; text-align: center; }}
    QProgressBar::chunk {{ background: {p.acento}; border-radius: 5px; }}
    QTableWidget, QTextEdit, QTextBrowser, QListWidget, QGraphicsView, QLineEdit {{
        background: {p.panel}; border: 1px solid {p.borde}; border-radius: 8px;
        gridline-color: {p.borde}; selection-background-color: {p.acento_suave}; selection-color: {p.texto};
    }}
    QHeaderView::section {{
        background: {p.lateral}; border: none; border-bottom: 1px solid {p.borde};
        padding: 8px; font-weight: 600; color: {p.texto_suave};
    }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator, QTableView::indicator {{
        width: 16px; height: 16px; border-radius: 4px;
        border: 1.5px solid {p.texto_suave}; background: {p.panel};
    }}
    QCheckBox::indicator:hover, QTableView::indicator:hover {{ border-color: {p.acento}; }}
    QCheckBox::indicator:checked, QTableView::indicator:checked {{
        background: {p.acento}; border-color: {p.acento}; image: url("{marca}");
    }}
    QCheckBox::indicator:disabled, QTableView::indicator:disabled {{ border-color: {p.borde}; background: {p.lateral}; }}
    QPushButton:pressed {{ background: {p.acento_suave}; }}
    QPushButton#primario:pressed {{ background: {p.acento}; padding-top: 1px; }}
    QPushButton:focus, QLineEdit:focus {{ border: 2px solid {p.acento}; }}
    QPushButton#primario:focus {{ border: 2px solid {p.texto}; }}
    QPushButton#nav:focus {{ border: 2px solid {p.acento}; }}
    QPushButton#primario:disabled {{ background: {p.borde}; color: {p.texto_suave}; }}
    QPushButton#peligro:disabled {{ color: {p.texto_suave}; border-color: {p.borde}; }}
    QLineEdit {{ min-height: 34px; padding: 0 10px; }}
    QTableWidget::item {{ padding: 0 6px; }}
    QTableWidget::item:selected {{ background: {p.acento_suave}; color: {p.texto}; }}
    QToolTip {{ background: {p.panel}; color: {p.texto}; border: 1px solid {p.borde}; padding: 6px; }}
    QStatusBar {{ background: {p.lateral}; color: {p.texto_suave}; border-top: 1px solid {p.borde}; }}
    QSplitter::handle {{ background: transparent; width: 8px; }}
    #logo {{ background: {p.acento}; color: {p.acento_texto}; border-radius: 6px; font-weight: 800; font-size: 9pt; }}
    #marca {{ font-size: 13pt; font-weight: 700; }}
    #zonaIcono {{ background: {p.acento_suave}; border-radius: 36px; }}
    #seccion {{ color: {p.texto_suave}; font-size: 9pt; font-weight: 700; letter-spacing: 0.5px; }}
    """
