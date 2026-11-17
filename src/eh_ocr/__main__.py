"""Punto de entrada de eh-ocr (doble clic en eh-ocr.exe)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _configurar_registro() -> None:
    from . import config

    ruta = config.carpeta_datos() / "registro.log"
    manejador = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    # El registro nunca guarda el contenido de los documentos: solo eventos y errores.
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[manejador])


def autoprueba(destino: Path) -> int:
    """Verificación del paquete construido (usada por la construcción automática).

    Genera una página con texto, la reconoce sin internet y escribe el resultado.
    """
    import tempfile

    from PIL import Image, ImageDraw, ImageFont

    from .metricas import cer
    from .pipeline import Motores, procesar_documento

    texto = [
        "eh-ocr autoprueba: El niño comió pequeñas porciones.",
        "Die Größe der Brücke überrascht über 50 Männer.",
        "The quick brown fox jumps over the lazy dog 2026.",
    ]
    fuente = None
    for nombre in ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"):
        if Path(nombre).exists():
            fuente = ImageFont.truetype(nombre, 40)
            break
    im = Image.new("RGB", (2480, 1200), "white")
    d = ImageDraw.Draw(im)
    for i, linea in enumerate(texto):
        d.text((150, 200 + i * 100), linea, font=fuente or ImageFont.load_default(40), fill="black")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "autoprueba.png"
        im.rotate(1.5, fillcolor="white").save(ruta, dpi=(300, 300))
        try:
            r = procesar_documento(ruta)
            error = cer("\n".join(texto), r.texto)
            m = Motores.obtener().estado()
            ok = error < 0.03 and m["rapidocr"] and m["tesseract"]
            informe = f"{'OK' if ok else 'FALLO'} cer={error:.4f} motores={m}\n{r.texto}\n"
        except Exception as e:  # noqa: BLE001
            ok, informe = False, f"FALLO excepción: {e!r}\n"
    destino.write_text(informe, encoding="utf-8")
    return 0 if ok else 1


def main() -> int:
    from .red import bloquear_red

    bloquear_red()  # absolutamente autónomo: ninguna conexión de red
    if len(sys.argv) >= 3 and sys.argv[1] == "--autoprueba":
        return autoprueba(Path(sys.argv[2]))
    try:
        _configurar_registro()
    except OSError:
        pass

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from . import config
    from .ui.ventana import VentanaPrincipal

    app = QApplication(sys.argv)
    app.setApplicationName("eh-ocr")
    app.setOrganizationName("eh")
    icono = config.carpeta_recursos() / "eh-ocr.ico"
    if icono.exists():
        app.setWindowIcon(QIcon(str(icono)))
    ventana = VentanaPrincipal()
    ventana.show()
    # Archivos arrastrados sobre eh-ocr.exe
    archivos = [Path(a) for a in sys.argv[1:] if Path(a).exists()]
    if archivos:
        ventana.agregar_archivos(archivos)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
