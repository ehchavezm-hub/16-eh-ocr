"""Estructuras de datos compartidas por todo eh-ocr."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class TipoPagina(str, Enum):
    DIGITAL = "digital"        # PDF con texto digital: no necesita OCR
    ESCANEO = "escaneo"        # imagen de escáner
    FOTO = "foto"              # foto de celular (perspectiva, iluminación)


class EstadoPagina(str, Enum):
    OK = "ok"
    DUDOSA = "dudosa"              # tiene palabras de baja confianza
    NO_PROCESADA = "no_procesada"  # falló también el modo rápido (se puede reprocesar)


@dataclass
class Palabra:
    texto: str
    confianza: float                     # 0..1
    caja: tuple[float, float, float, float]  # x0, y0, x1, y1 en píxeles de la imagen de trabajo
    motor: str = ""
    alternativas: dict[str, str] = field(default_factory=dict)  # motor -> lectura
    corregida_de: str | None = None      # texto original si el corrector la cambió
    dudosa: bool = False

    @property
    def cx(self) -> float:
        return (self.caja[0] + self.caja[2]) / 2

    @property
    def cy(self) -> float:
        return (self.caja[1] + self.caja[3]) / 2

    @property
    def alto(self) -> float:
        return self.caja[3] - self.caja[1]


@dataclass
class Linea:
    palabras: list[Palabra]

    @property
    def texto(self) -> str:
        return " ".join(p.texto for p in self.palabras)

    @property
    def caja(self) -> tuple[float, float, float, float]:
        return (
            min(p.caja[0] for p in self.palabras),
            min(p.caja[1] for p in self.palabras),
            max(p.caja[2] for p in self.palabras),
            max(p.caja[3] for p in self.palabras),
        )


@dataclass
class PerfilPagina:
    numero: int                      # 1-based
    tipo: TipoPagina
    ancho_px: int
    alto_px: int
    dpi: float
    ancho_pt: float                  # tamaño físico para el PDF de salida
    alto_pt: float
    inclinacion: float = 0.0         # grados corregidos
    rotacion: int = 0                # 0/90/180/270 corregidos
    contraste: float = 0.0
    caracteres_digitales: int = 0


@dataclass
class ResultadoPagina:
    perfil: PerfilPagina
    lineas: list[Linea]
    estado: EstadoPagina
    motores: list[str]
    confianza_media: float
    segundos: float
    idioma: str = ""
    mensaje: str = ""
    tablas: list = field(default_factory=list)  # list[tablas.Tabla]

    @property
    def texto(self) -> str:
        return "\n".join(l.texto for l in self.lineas)

    def bloques(self) -> list[tuple[str, object]]:
        """Contenido en orden de lectura: ("linea", Linea) o ("tabla", Tabla).

        Las líneas cuyas palabras pertenecen a una tabla no se repiten como texto suelto.
        """
        if not self.tablas:
            return [("linea", l) for l in self.lineas]
        en_tabla = {i for t in self.tablas for c in t.celdas for i in c.indices}
        salida: list[tuple[float, str, object]] = []
        k = 0
        for l in self.lineas:
            libres = []
            for p in l.palabras:
                if k not in en_tabla:
                    libres.append(p)
                k += 1
            if libres:
                linea = Linea(libres)
                salida.append((linea.caja[1], "linea", linea))
        for t in self.tablas:
            salida.append((t.caja[1], "tabla", t))
        salida.sort(key=lambda x: x[0])
        return [(tipo, obj) for _, tipo, obj in salida]

    @property
    def palabras(self) -> list[Palabra]:
        return [p for l in self.lineas for p in l.palabras]

    @property
    def dudosas(self) -> list[Palabra]:
        return [p for p in self.palabras if p.dudosa]

    def a_dict(self) -> dict:
        d = asdict(self)
        d["perfil"]["tipo"] = self.perfil.tipo.value
        d["estado"] = self.estado.value
        return d

    @staticmethod
    def de_dict(d: dict) -> "ResultadoPagina":
        perfil = dict(d["perfil"])
        perfil["tipo"] = TipoPagina(perfil["tipo"])
        lineas = [
            Linea([Palabra(**{**p, "caja": tuple(p["caja"])}) for p in l["palabras"]])
            for l in d["lineas"]
        ]
        return ResultadoPagina(
            perfil=PerfilPagina(**perfil),
            lineas=lineas,
            estado=EstadoPagina(d["estado"]),
            motores=list(d["motores"]),
            confianza_media=d["confianza_media"],
            segundos=d["segundos"],
            idioma=d.get("idioma", ""),
            mensaje=d.get("mensaje", ""),
            tablas=_tablas_de_dict(d.get("tablas", [])),
        )


def _tablas_de_dict(datos: list) -> list:
    if not datos:
        return []
    from .tablas import Tabla

    return [Tabla.de_dict(t) for t in datos]


@dataclass
class ResultadoDocumento:
    origen: str
    paginas: list[ResultadoPagina]
    segundos: float = 0.0
    salidas: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n\n".join(p.texto for p in self.paginas)

    @property
    def confianza_media(self) -> float:
        pals = [w for p in self.paginas for w in p.palabras]
        if not pals:
            return 0.0
        return sum(w.confianza for w in pals) / len(pals)

    @property
    def paginas_dudosas(self) -> list[int]:
        return [p.perfil.numero for p in self.paginas if p.estado == EstadoPagina.DUDOSA]

    @property
    def paginas_no_procesadas(self) -> list[int]:
        return [p.perfil.numero for p in self.paginas if p.estado == EstadoPagina.NO_PROCESADA]
