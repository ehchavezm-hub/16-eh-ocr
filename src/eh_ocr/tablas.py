"""Detección y estructura de tablas.

Capas, de la más exacta a la más general:
  1. PDF digital: tablas de pdfplumber (líneas del propio PDF), exactas e instantáneas.
  2. Tablas con bordes en imágenes: se detectan las líneas con OpenCV y se arma la
     cuadrícula, incluidas las celdas combinadas.
  3. Tablas sin bordes: RapidLayout encuentra la región y RapidTable (SLANet+) reconoce
     filas, columnas y celdas combinadas.
  4. Respaldo: filas por renglón y columnas por alineación del texto.

Las celdas no copian el texto: guardan índices a las palabras de la página. Así, las
correcciones hechas en la revisión aparecen también en las tablas de Word y Excel.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from . import config
from .modelo import Palabra

log = logging.getLogger(__name__)

Caja = tuple[float, float, float, float]


@dataclass
class Celda:
    fila: int
    col: int
    filas: int  # filas que ocupa (celdas combinadas)
    cols: int
    caja: Caja
    indices: list[int] = field(default_factory=list)  # palabras de la página


@dataclass
class Tabla:
    caja: Caja
    n_filas: int
    n_cols: int
    celdas: list[Celda]
    metodo: str  # "pdf", "bordes", "modelo", "alineacion"

    def a_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def de_dict(d: dict) -> "Tabla":
        return Tabla(
            caja=tuple(d["caja"]),
            n_filas=d["n_filas"],
            n_cols=d["n_cols"],
            celdas=[Celda(**{**c, "caja": tuple(c["caja"])}) for c in d["celdas"]],
            metodo=d["metodo"],
        )


# --- utilidades -----------------------------------------------------------------

def _centro(c: Caja) -> tuple[float, float]:
    return (c[0] + c[2]) / 2, (c[1] + c[3]) / 2


def _dentro(punto: tuple[float, float], c: Caja, margen: float = 0) -> bool:
    return c[0] - margen <= punto[0] <= c[2] + margen and c[1] - margen <= punto[1] <= c[3] + margen


def _iou(a: Caja, b: Caja) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


def _agrupar(valores: list[float], tolerancia: float) -> list[float]:
    grupos: list[list[float]] = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [sum(g) / len(g) for g in grupos]


def asignar_palabras(tabla: Tabla, palabras: list[Palabra]) -> set[int]:
    """Pone cada palabra cuyo centro cae en la tabla dentro de su celda. Devuelve los índices usados."""
    usados: set[int] = set()
    for i, p in enumerate(palabras):
        c = (p.cx, p.cy)
        if not _dentro(c, tabla.caja, margen=p.alto * 0.3):
            continue
        destino = next((cel for cel in tabla.celdas if _dentro(c, cel.caja)), None)
        if destino is None:  # entre celdas: la más cercana
            destino = min(tabla.celdas, key=lambda cel: (_centro(cel.caja)[0] - c[0]) ** 2 + (_centro(cel.caja)[1] - c[1]) ** 2)
        destino.indices.append(i)
        usados.add(i)
    for cel in tabla.celdas:
        cel.indices = _orden_lectura(cel.indices, palabras)
    return usados


def _orden_lectura(indices: list[int], palabras: list[Palabra]) -> list[int]:
    """Renglón por renglón (por solapamiento vertical) y de izquierda a derecha."""
    renglones: list[list[int]] = []
    for i in sorted(indices, key=lambda i: palabras[i].cy):
        p = palabras[i]
        if renglones:
            ultimo = [palabras[k] for k in renglones[-1]]
            y0 = min(w.caja[1] for w in ultimo)
            y1 = max(w.caja[3] for w in ultimo)
            if min(y1, p.caja[3]) - max(y0, p.caja[1]) > 0.5 * min(y1 - y0, max(p.alto, 1)):
                renglones[-1].append(i)
                continue
        renglones.append([i])
    return [i for r in renglones for i in sorted(r, key=lambda k: palabras[k].caja[0])]


def texto_celda(celda: Celda, palabras: list[Palabra]) -> str:
    return " ".join(palabras[i].texto for i in celda.indices if i < len(palabras))


def celda_dudosa(celda: Celda, palabras: list[Palabra]) -> bool:
    return any(palabras[i].dudosa for i in celda.indices if i < len(palabras))


def _tabla_valida(t: Tabla, palabras: list[Palabra]) -> bool:
    """Descarta falsos positivos: una "tabla" de una sola columna o casi vacía no es tabla."""
    if t.n_cols < 2 or t.n_filas < 2:
        return False
    con_texto = sum(1 for c in t.celdas if c.indices)
    return con_texto >= 3


# --- cuadrícula a partir de bordes/aristas -------------------------------------------

def _cuadricula(ys: list[float], xs: list[float], separa_derecha, separa_abajo, offset=(0.0, 0.0)) -> list[Celda]:
    """Celdas a partir de líneas de filas (ys) y columnas (xs), uniendo las que no tienen separador."""
    nf, nc = len(ys) - 1, len(xs) - 1
    padre = list(range(nf * nc))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for r in range(nf):
        for c in range(nc):
            if c + 1 < nc and not separa_derecha(r, c):
                padre[raiz(r * nc + c + 1)] = raiz(r * nc + c)
            if r + 1 < nf and not separa_abajo(r, c):
                padre[raiz((r + 1) * nc + c)] = raiz(r * nc + c)
    grupos: dict[int, list[tuple[int, int]]] = {}
    for r in range(nf):
        for c in range(nc):
            grupos.setdefault(raiz(r * nc + c), []).append((r, c))
    ox, oy = offset
    celdas = []
    for miembros in grupos.values():
        r0, r1 = min(m[0] for m in miembros), max(m[0] for m in miembros)
        c0, c1 = min(m[1] for m in miembros), max(m[1] for m in miembros)
        if len(miembros) != (r1 - r0 + 1) * (c1 - c0 + 1):
            # grupo irregular (en L, por una línea cortada): una celda por casilla
            for r, c in miembros:
                celdas.append(Celda(r, c, 1, 1, (xs[c] + ox, ys[r] + oy, xs[c + 1] + ox, ys[r + 1] + oy)))
            continue
        celdas.append(Celda(r0, c0, r1 - r0 + 1, c1 - c0 + 1, (xs[c0] + ox, ys[r0] + oy, xs[c1 + 1] + ox, ys[r1 + 1] + oy)))
    celdas.sort(key=lambda c: (c.fila, c.col))
    return celdas


def tablas_por_bordes(imagen: np.ndarray) -> list[Tabla]:
    """Tablas con líneas visibles (las más comunes en contratos, metrados y presupuestos)."""
    g = cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY) if imagen.ndim == 3 else imagen
    b = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    h, w = b.shape
    horiz = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, w // 25), 1)))
    vert = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, h // 40))))
    # cerrar pequeñas interrupciones de las líneas (escaneos)
    horiz = cv2.dilate(horiz, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)))
    vert = cv2.dilate(vert, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9)))
    reja = cv2.bitwise_or(horiz, vert)
    contornos, _ = cv2.findContours(reja, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tablas = []
    for cnt in contornos:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw < w * 0.15 or ch < 40:
            continue
        hz = horiz[y : y + ch, x : x + cw]
        vt = vert[y : y + ch, x : x + cw]
        n_h, lab_h, st_h, _ = cv2.connectedComponentsWithStats(hz)
        n_v, lab_v, st_v, _ = cv2.connectedComponentsWithStats(vt)
        ys = _agrupar([st_h[i, 1] + st_h[i, 3] / 2 for i in range(1, n_h)], 10)
        xs = _agrupar([st_v[i, 0] + st_v[i, 2] / 2 for i in range(1, n_v)], 10)
        # bordes exteriores aunque falte la línea
        if not ys or ys[0] > 15:
            ys = [0.0] + ys
        if ys[-1] < ch - 15:
            ys = ys + [float(ch)]
        if not xs or xs[0] > 15:
            xs = [0.0] + xs
        if xs[-1] < cw - 15:
            xs = xs + [float(cw)]
        if len(ys) < 3 or len(xs) < 3:
            continue

        def separa_derecha(r, c):
            xx = xs[c + 1]
            alto = ys[r + 1] - ys[r]
            zona = vt[int(ys[r] + alto * 0.2) : int(ys[r + 1] - alto * 0.2), max(0, int(xx) - 5) : int(xx) + 6]
            return zona.size > 0 and (zona.max(axis=1) > 0).mean() > 0.5

        def separa_abajo(r, c):
            yy = ys[r + 1]
            ancho = xs[c + 1] - xs[c]
            zona = hz[max(0, int(yy) - 5) : int(yy) + 6, int(xs[c] + ancho * 0.2) : int(xs[c + 1] - ancho * 0.2)]
            return zona.size > 0 and (zona.max(axis=0) > 0).mean() > 0.5

        celdas = _cuadricula(ys, xs, separa_derecha, separa_abajo, offset=(x, y))
        tablas.append(Tabla((float(x), float(y), float(x + cw), float(y + ch)), len(ys) - 1, len(xs) - 1, celdas, "bordes"))
    return tablas


def tabla_por_alineacion(region: Caja, palabras: list[Palabra]) -> Tabla | None:
    """Respaldo: filas por renglón y columnas por alineación (tablas sin bordes)."""
    dentro = [p for p in palabras if _dentro((p.cx, p.cy), region)]
    if len(dentro) < 4:
        return None
    alto = float(np.median([p.alto for p in dentro]))
    ys = _agrupar([p.cy for p in dentro], alto * 0.6)
    # segmentos: palabras separadas por un hueco grande
    filas_seg: list[list[list[Palabra]]] = []
    for yc in ys:
        fila = sorted([p for p in dentro if abs(p.cy - yc) <= alto * 0.6], key=lambda p: p.caja[0])
        segs: list[list[Palabra]] = []
        for p in fila:
            if segs and p.caja[0] - segs[-1][-1].caja[2] <= alto * 1.5:
                segs[-1].append(p)
            else:
                segs.append([p])
        filas_seg.append(segs)
    inicios = _agrupar([s[0].caja[0] for f in filas_seg for s in f], max(alto * 2, (region[2] - region[0]) * 0.03))
    if len(inicios) < 2:
        return None
    xs = [region[0]] + [(inicios[k] + inicios[k + 1]) / 2 - alto for k in range(len(inicios) - 1)] + [region[2]]
    bordes_y = [region[1]] + [(ys[k] + ys[k + 1]) / 2 for k in range(len(ys) - 1)] + [region[3]]
    celdas = _cuadricula(bordes_y, xs, lambda r, c: True, lambda r, c: True)
    return Tabla(region, len(bordes_y) - 1, len(xs) - 1, celdas, "alineacion")


# --- modelos (RapidLayout + RapidTable) -------------------------------------------------

class ModelosTablas:
    """Carga perezosa de los modelos; si faltan, eh-ocr sigue con bordes y alineación.

    Alta precisión (incluida en el paquete):
      - Zonas: PP-DocLayout v3 (respaldo: modelo general incluido en rapid_layout).
      - Estructura: SLANet+ y SLANet en inglés; se comparan entre sí y con la alineación.
    """

    ESTRUCTURAS = (("slanet-plus.onnx", "SLANETPLUS"), ("slanet-en.onnx", "PPSTRUCTURE_EN"))

    _instancia: "ModelosTablas | None" = None
    _lock_clase = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._layout = None
        self.layout_preciso = False
        self._tablas: list = []
        self._cargado = False

    @classmethod
    def obtener(cls) -> "ModelosTablas":
        with cls._lock_clase:
            if cls._instancia is None:
                cls._instancia = ModelosTablas()
            return cls._instancia

    def _cargar(self) -> None:
        if self._cargado:
            return
        self._cargado = True
        carpeta = config.carpeta_modelos() / "tablas"
        try:
            from rapid_layout import ModelType as TipoLayout
            from rapid_layout import RapidLayout, RapidLayoutInput

            preciso = carpeta / "pp_doc_layoutv3.onnx"
            if preciso.exists():
                try:
                    self._layout = RapidLayout(cfg=RapidLayoutInput(
                        model_type=TipoLayout.PP_DOC_LAYOUTV3, model_dir_or_path=str(preciso), conf_thresh=0.5))
                    self.layout_preciso = True
                except Exception as e:
                    log.warning("PP-DocLayout no pudo iniciarse (%s); se usa el modelo general", e)
            if self._layout is None:
                self._layout = RapidLayout(cfg=RapidLayoutInput(model_type=TipoLayout.PP_LAYOUT_CDLA, conf_thresh=0.5))
        except Exception as e:
            log.warning("Detector de tablas (RapidLayout) no disponible: %s", e)
        try:
            from rapid_table import ModelType as TipoTabla
            from rapid_table import RapidTable, RapidTableInput
        except Exception as e:
            log.warning("Estructura de tablas (RapidTable) no disponible: %s", e)
            return
        for archivo, tipo in self.ESTRUCTURAS:
            ruta = carpeta / archivo
            if not ruta.exists():
                continue
            try:
                self._tablas.append(RapidTable(RapidTableInput(
                    model_type=getattr(TipoTabla, tipo), model_dir_or_path=str(ruta), use_ocr=False)))
            except Exception as e:
                log.warning("Modelo de tablas %s no pudo iniciarse: %s", archivo, e)

    @property
    def estado(self) -> dict:
        with self._lock:
            self._cargar()
        return {
            "layout": self._layout is not None,
            "layout_preciso": self.layout_preciso,
            "estructura": bool(self._tablas),
            "estructuras": len(self._tablas),
        }

    def regiones(self, imagen: np.ndarray) -> list[Caja]:
        with self._lock:
            self._cargar()
            if self._layout is None:
                return []
            try:
                r = self._layout(imagen)
            except Exception as e:
                log.warning("RapidLayout falló: %s", e)
                return []
        salida = []
        for caja, nombre in zip(r.boxes or [], r.class_names or []):
            if str(nombre).lower() == "table":
                salida.append(tuple(float(v) for v in caja[:4]))
        return salida

    def estructuras(self, imagen: np.ndarray, region: Caja) -> list[Tabla]:
        """Una estructura candidata por cada modelo disponible."""
        x0, y0, x1, y1 = (int(v) for v in region)
        recorte = imagen[max(0, y0) : y1, max(0, x0) : x1]
        if recorte.size == 0:
            return []
        candidatos = []
        with self._lock:
            self._cargar()
            modelos = list(self._tablas)
        for modelo in modelos:
            with self._lock:
                try:
                    r = modelo(recorte)
                except Exception as e:
                    log.warning("RapidTable falló: %s", e)
                    continue
            t = _tabla_desde_modelo(r, region, x0, y0)
            if t is not None:
                candidatos.append(t)
        return candidatos

    def estructura(self, imagen: np.ndarray, region: Caja) -> Tabla | None:
        """Compatibilidad: la primera estructura disponible."""
        cands = self.estructuras(imagen, region)
        return cands[0] if cands else None


def _tabla_desde_modelo(r, region: Caja, x0: int, y0: int) -> Tabla | None:
    if not r.cell_bboxes or not r.logic_points:
        return None
    cajas, logicos = np.asarray(r.cell_bboxes[0]), np.asarray(r.logic_points[0])
    celdas = []
    for caja, lp in zip(cajas, logicos):
        caja = np.asarray(caja, dtype=float).reshape(-1, 2)
        f0, f1, c0, c1 = (int(v) for v in lp[:4])
        celdas.append(
            Celda(f0, c0, f1 - f0 + 1, c1 - c0 + 1,
                  (caja[:, 0].min() + x0, caja[:, 1].min() + y0, caja[:, 0].max() + x0, caja[:, 1].max() + y0))
        )
    if not celdas:
        return None
    n_f = max(c.fila + c.filas for c in celdas)
    n_c = max(c.col + c.cols for c in celdas)
    return Tabla(tuple(float(v) for v in region), n_f, n_c, celdas, "modelo")


# --- API principal -------------------------------------------------------------------------

def detectar_en_imagen(imagen: np.ndarray, palabras_trabajo: list[Palabra]) -> list[Tabla]:
    """Tablas en una imagen ya enderezada; las cajas quedan en coordenadas de esa imagen."""
    tablas = tablas_por_bordes(imagen)
    modelos = ModelosTablas.obtener()
    for region in modelos.regiones(imagen):
        if any(_iou(region, t.caja) > 0.3 for t in tablas):
            continue  # ya detectada por sus bordes (más exacto)
        candidatos = [
            c for c in [*modelos.estructuras(imagen, region), tabla_por_alineacion(region, palabras_trabajo)]
            if c is not None and c.n_cols >= 2 and c.n_filas >= 2 and len(c.celdas) >= 4
        ]
        t = _mejor_candidato(candidatos, palabras_trabajo)
        if t is not None:
            tablas.append(t)
    return tablas


def normalizar(t: Tabla) -> Tabla:
    """Garantiza una cuadrícula válida: celdas dentro de la tabla y sin superposiciones.

    Una celda que se superpone con otra ya ubicada se recorta a su primera posición libre
    o se descarta (sus palabras irán a la celda más cercana). Así Word y Excel nunca reciben
    combinaciones imposibles.
    """
    ocupadas: set[tuple[int, int]] = set()
    limpias: list[Celda] = []
    for c in sorted(t.celdas, key=lambda c: (c.fila, c.col, -(c.filas * c.cols))):
        if not (0 <= c.fila < t.n_filas and 0 <= c.col < t.n_cols):
            continue
        filas = max(1, min(c.filas, t.n_filas - c.fila))
        cols = max(1, min(c.cols, t.n_cols - c.col))
        if (c.fila, c.col) in ocupadas:
            continue
        # achicar el rango hasta que no choque con celdas ya ubicadas
        while cols > 1 and any((c.fila + r, c.col + k) in ocupadas for r in range(filas) for k in range(cols)):
            cols -= 1
        while filas > 1 and any((c.fila + r, c.col + k) in ocupadas for r in range(filas) for k in range(cols)):
            filas -= 1
        if any((c.fila + r, c.col + k) in ocupadas for r in range(filas) for k in range(cols)):
            continue
        for r in range(filas):
            for k in range(cols):
                ocupadas.add((c.fila + r, c.col + k))
        c.filas, c.cols = filas, cols
        limpias.append(c)
    t.celdas = limpias
    return t


def huecos_internos(t: Tabla, palabras: list[Palabra]) -> int:
    """Cuántas celdas tienen palabras muy separadas en un mismo renglón: señal de columnas juntadas."""
    malas = 0
    for c in t.celdas:
        ps = [palabras[i] for i in c.indices]
        for a in ps:
            for b in ps:
                if a is b or abs(a.cy - b.cy) > 0.5 * max(a.alto, 1):
                    continue
                if 0 < b.caja[0] - a.caja[2] > 2.5 * max(a.alto, b.alto, 1):
                    malas += 1
                    break
            else:
                continue
            break
    return malas


def _mejor_candidato(candidatos: list[Tabla], palabras: list[Palabra]) -> Tabla | None:
    """Arma la tabla con cada método y elige la que no junta columnas.

    Empate: gana la del modelo (reconoce celdas combinadas). Más columnas reales también desempatan.
    """
    import copy

    mejor, mejor_puntaje = None, None
    for orden, cand in enumerate(candidatos):
        prueba = normalizar(copy.deepcopy(cand))
        asignar_palabras(prueba, palabras)
        puntaje = (huecos_internos(prueba, palabras), -prueba.n_cols, orden)
        if mejor_puntaje is None or puntaje < mejor_puntaje:
            mejor, mejor_puntaje = cand, puntaje
    return mejor


def _escalar(t: Tabla, f: float) -> Tabla:
    t.caja = tuple(v * f for v in t.caja)
    for c in t.celdas:
        c.caja = tuple(v * f for v in c.caja)
    return t


def detectar_sin_bordes_digital(
    imagen: np.ndarray, palabras: list[Palabra], ya: list[Tabla], escala: float = 1.0
) -> list[Tabla]:
    """PDF digital: tablas SIN líneas (pdfplumber no las ve). Zonas por el detector,
    texto exacto del PDF. Se omiten las zonas ya cubiertas por tablas con líneas.

    `escala`: de la imagen analizada a las coordenadas de las palabras (p. ej. 150 → 300 ppp = 2).
    """
    modelos = ModelosTablas.obtener()
    salida = []
    for region_img in modelos.regiones(imagen):
        region = tuple(v * escala for v in region_img)
        if any(_iou(region, t.caja) > 0.3 for t in ya):
            continue
        candidatos = [_escalar(c, escala) for c in modelos.estructuras(imagen, region_img)]
        candidatos.append(tabla_por_alineacion(region, palabras))
        candidatos = [c for c in candidatos if c is not None and c.n_cols >= 2 and c.n_filas >= 2 and len(c.celdas) >= 4]
        t = _mejor_candidato(candidatos, palabras)
        if t is not None:
            salida.append(t)
    return salida


def finalizar(tablas: list[Tabla], palabras: list[Palabra]) -> list[Tabla]:
    """Asigna palabras (mismas coordenadas que las tablas) y descarta falsos positivos."""
    validas = []
    usados: set[int] = set()
    for t in sorted(tablas, key=lambda t: (t.caja[1], t.caja[0])):
        normalizar(t)
        if not t.celdas:
            continue
        libres = [p if i not in usados else Palabra("", 0, (-1e9, -1e9, -1e9, -1e9)) for i, p in enumerate(palabras)]
        nuevos = asignar_palabras(t, libres)
        if _tabla_valida(t, palabras):
            validas.append(t)
            usados |= nuevos
        else:
            for c in t.celdas:
                c.indices.clear()
    return validas
