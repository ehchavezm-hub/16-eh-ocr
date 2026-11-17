"""Preproceso de imágenes antes del OCR.

Cada transformación se acumula en una homografía H (original -> trabajo),
para poder devolver las cajas de las palabras a la página original al
generar el PDF con texto buscable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config


@dataclass
class ImagenTrabajo:
    imagen: np.ndarray                  # RGB uint8
    H: np.ndarray = field(default_factory=lambda: np.eye(3))  # original -> trabajo
    rotacion: int = 0
    inclinacion: float = 0.0
    pasos: list[str] = field(default_factory=list)

    def aplicar(self, nueva: np.ndarray, M: np.ndarray, paso: str) -> None:
        M3 = M if M.shape == (3, 3) else np.vstack([M, [0, 0, 1]])
        self.imagen = nueva
        self.H = M3 @ self.H
        self.pasos.append(paso)

    def a_original(self, caja: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        """Caja en la imagen de trabajo -> caja en la imagen original."""
        x0, y0, x1, y1 = caja
        pts = np.array([[[x0, y0]], [[x1, y0]], [[x1, y1]], [[x0, y1]]], dtype=np.float64)
        inv = np.linalg.inv(self.H)
        o = cv2.perspectiveTransform(pts, inv).reshape(-1, 2)
        return float(o[:, 0].min()), float(o[:, 1].min()), float(o[:, 0].max()), float(o[:, 1].max())


def a_gris(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img


def contraste(img: np.ndarray) -> float:
    """Diferencia entre la tinta y el papel (mediana), 0..1."""
    g = a_gris(img)
    umbral, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    tinta = g[g < umbral]
    if tinta.size == 0:
        return 0.0
    return float(np.median(g) - tinta.mean()) / 255.0


def iluminacion_despareja(img: np.ndarray) -> float:
    """Variación del fondo (papel) en niveles de gris: alta en fotos con sombras."""
    g = a_gris(img)
    escala = 400 / max(g.shape)
    if escala < 1:
        g = cv2.resize(g, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    fondo = cv2.GaussianBlur(cv2.dilate(g, np.ones((9, 9), np.uint8)), (0, 0), 15)
    return float(np.std(fondo))


# --- Orientación e inclinación ---------------------------------------------

def rotar_90(trabajo: ImagenTrabajo, grados: int) -> None:
    """Rota la imagen 90/180/270 grados en sentido horario."""
    grados %= 360
    if grados == 0:
        return
    img = trabajo.imagen
    h, w = img.shape[:2]
    if grados == 90:
        nueva = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        M = np.array([[0, -1, h - 1], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
    elif grados == 180:
        nueva = cv2.rotate(img, cv2.ROTATE_180)
        M = np.array([[-1, 0, w - 1], [0, -1, h - 1], [0, 0, 1]], dtype=np.float64)
    else:  # 270
        nueva = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        M = np.array([[0, 1, 0], [-1, 0, w - 1], [0, 0, 1]], dtype=np.float64)
    trabajo.aplicar(nueva, M, f"rotación {grados}°")
    trabajo.rotacion = grados


def estimar_inclinacion(img: np.ndarray, max_grados: float = 8.0) -> float:
    """Ángulo (grados) que maximiza la nitidez del perfil horizontal de líneas."""
    g = a_gris(img)
    escala = 1000 / max(g.shape)
    if escala < 1:
        g = cv2.resize(g, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if b.mean() < 1:  # página vacía
        return 0.0
    h, w = b.shape
    centro = (w / 2, h / 2)

    def puntaje(angulo: float) -> float:
        M = cv2.getRotationMatrix2D(centro, angulo, 1.0)
        r = cv2.warpAffine(b, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        perfil = r.sum(axis=1, dtype=np.float64)
        return float(np.var(np.diff(perfil)))

    mejor, mejor_p = 0.0, puntaje(0.0)
    for paso, rango in ((0.5, max_grados), (0.1, 0.5)):
        base = mejor
        for a in np.arange(base - rango, base + rango + 1e-9, paso):
            p = puntaje(float(a))
            if p > mejor_p:
                mejor, mejor_p = float(a), p
    return round(mejor, 2)


def enderezar(trabajo: ImagenTrabajo, angulo: float) -> None:
    if abs(angulo) < 0.1:
        return
    img = trabajo.imagen
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    nueva = cv2.warpAffine(img, M, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    trabajo.aplicar(nueva, M, f"enderezado {angulo:+.1f}°")
    trabajo.inclinacion = angulo


# --- Fotos de celular ------------------------------------------------------

def _ordenar_esquinas(p: np.ndarray) -> np.ndarray:
    s = p.sum(axis=1)
    d = np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]], dtype=np.float32)


def corregir_perspectiva(trabajo: ImagenTrabajo) -> bool:
    """Si se detecta el borde de la hoja, la recorta y la pone de frente."""
    img = trabajo.imagen
    h, w = img.shape[:2]
    escala = 800 / max(h, w)
    peq = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(a_gris(peq), (5, 5), 0)
    bordes = cv2.dilate(cv2.Canny(g, 50, 150), np.ones((3, 3), np.uint8))
    contornos, _ = cv2.findContours(bordes, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_min = 0.3 * peq.shape[0] * peq.shape[1]
    for c in sorted(contornos, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < area_min:
            break
        aprox = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(aprox) != 4:
            continue
        esq = _ordenar_esquinas(aprox.reshape(4, 2) / escala)
        ancho = int(max(np.linalg.norm(esq[2] - esq[3]), np.linalg.norm(esq[1] - esq[0])))
        alto = int(max(np.linalg.norm(esq[1] - esq[2]), np.linalg.norm(esq[0] - esq[3])))
        if ancho < 200 or alto < 200:
            continue
        destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(esq, destino)
        nueva = cv2.warpPerspective(img, M, (ancho, alto), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
        trabajo.aplicar(nueva, M.astype(np.float64), "perspectiva corregida")
        return True
    return False


def normalizar_iluminacion(trabajo: ImagenTrabajo) -> None:
    """Quita sombras y luz despareja dividiendo por el fondo estimado."""
    img = trabajo.imagen
    salida = np.empty_like(img)
    k = max(31, (max(img.shape[:2]) // 25) | 1)
    for c in range(3):
        canal = img[:, :, c]
        fondo = cv2.medianBlur(cv2.dilate(canal, np.ones((7, 7), np.uint8)), min(k, 255))
        salida[:, :, c] = cv2.divide(canal, fondo, scale=255)
    trabajo.aplicar(salida, np.eye(3), "iluminación normalizada")


# --- Mejora general ---------------------------------------------------------

def ampliar_si_baja_resolucion(trabajo: ImagenTrabajo, dpi: float, objetivo: float = config.DPI_MINIMO) -> None:
    if dpi >= objetivo * 0.95:
        return
    f = min(objetivo / max(dpi, 1), 3.0)
    nueva = cv2.resize(trabajo.imagen, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    trabajo.aplicar(nueva, np.diag([f, f, 1.0]), f"ampliada ×{f:.1f}")


def mejorar_contraste(trabajo: ImagenTrabajo) -> None:
    lab = cv2.cvtColor(trabajo.imagen, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    trabajo.aplicar(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), np.eye(3), "contraste")


def nivel_ruido(img: np.ndarray) -> float:
    g = a_gris(img)
    return float(np.mean(cv2.absdiff(g, cv2.medianBlur(g, 3))))


def quitar_ruido(trabajo: ImagenTrabajo) -> None:
    if nivel_ruido(trabajo.imagen) < 6:
        return
    nueva = cv2.fastNlMeansDenoisingColored(trabajo.imagen, None, 7, 7, 7, 21)
    trabajo.aplicar(nueva, np.eye(3), "ruido reducido")


def binarizar(trabajo: ImagenTrabajo) -> None:
    g = a_gris(trabajo.imagen)
    bloque = max(15, (min(g.shape) // 40) | 1)
    b = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bloque, 15)
    trabajo.aplicar(cv2.cvtColor(b, cv2.COLOR_GRAY2RGB), np.eye(3), "binarizada")


def escalar(trabajo: ImagenTrabajo, f: float) -> None:
    nueva = cv2.resize(trabajo.imagen, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    trabajo.aplicar(nueva, np.diag([f, f, 1.0]), f"escala ×{f:.1f}")


def copiar(trabajo: ImagenTrabajo) -> ImagenTrabajo:
    return ImagenTrabajo(
        imagen=trabajo.imagen.copy(),
        H=trabajo.H.copy(),
        rotacion=trabajo.rotacion,
        inclinacion=trabajo.inclinacion,
        pasos=list(trabajo.pasos),
    )


# Variantes que se prueban cuando la confianza es baja.
VARIANTES = ("estandar", "binaria", "ampliada")


def variante(base: ImagenTrabajo, nombre: str) -> ImagenTrabajo:
    t = copiar(base)
    if nombre == "binaria":
        binarizar(t)
    elif nombre == "ampliada":
        escalar(t, 1.5)
    return t
