"""Colores y hoja de estilo (claro/oscuro según Windows)."""

from __future__ import annotations

from dataclasses import dataclass


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


def qss(p: Paleta) -> str:
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
    QCheckBox {{ spacing: 6px; }}
    """
