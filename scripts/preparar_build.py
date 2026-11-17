"""Descarga y prepara los recursos que van DENTRO del paquete (solo en la construcción).

eh-ocr nunca se conecta a internet; esto se ejecuta una sola vez, en la
máquina que construye el paquete, y deja todo en recursos/:

  recursos/modelos/rapidocr/PP-OCRv6_{det,rec}_medium.onnx   (verificados por SHA256)
  recursos/modelos/tablas/slanet-plus.onnx                    (estructura de tablas, SHA256)
  recursos/tesseract/tesseract.exe + DLL                      (copiados de la instalación)
  recursos/tesseract/tessdata/{spa,eng,deu}.traineddata       (tessdata_best)
  recursos/tesseract/tessdata/osd.traineddata                 (detección de orientación)

Uso:  python scripts/preparar_build.py [--tesseract "C:\\Program Files\\Tesseract-OCR"]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RECURSOS = RAIZ / "recursos"

TESSDATA_BEST = "https://github.com/tesseract-ocr/tessdata_best/raw/main/{}.traineddata"
TESSDATA_OSD = "https://github.com/tesseract-ocr/tessdata/raw/main/osd.traineddata"
IDIOMAS = ("spa", "eng", "deu")


def descargar(url: str, destino: Path, sha256: str | None = None) -> None:
    if destino.exists() and (sha256 is None or _sha(destino) == sha256.lower()):
        print(f"  ya existe: {destino.name}")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    print(f"  descargando {url}")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if sha256 and _sha(tmp) != sha256.lower():
        tmp.unlink()
        raise SystemExit(f"SHA256 incorrecto para {url}")
    tmp.replace(destino)


def _sha(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def modelos_rapidocr() -> None:
    """Modelos PP-OCRv6 medium: URL y SHA256 tomados del catálogo oficial de RapidOCR."""
    import rapidocr
    import yaml

    catalogo = yaml.safe_load((Path(rapidocr.__file__).parent / "default_models.yaml").read_text(encoding="utf-8"))
    onnx = catalogo["onnxruntime"]["PP-OCRv6"]
    destino = RECURSOS / "modelos" / "rapidocr"
    for tarea, clave in (("det", "multi_PP-OCRv6_det_medium"), ("rec", "multi_PP-OCRv6_rec_medium")):
        info = onnx[tarea][clave]
        url = info["model_dir"]
        descargar(url, destino / Path(url).name, info.get("SHA256"))


def modelo_tablas() -> None:
    """SLANet+ (RapidTable): filas, columnas y celdas combinadas de tablas sin bordes."""
    import rapid_table
    import yaml

    catalogo = yaml.safe_load((Path(rapid_table.__file__).parent / "default_models.yaml").read_text(encoding="utf-8"))
    info = catalogo["slanet_plus"]
    descargar(info["model_dir_or_path"], RECURSOS / "modelos" / "tablas" / "slanet-plus.onnx", info.get("SHA256"))


def tesseract(origen: Path | None) -> None:
    destino = RECURSOS / "tesseract"
    tessdata = destino / "tessdata"
    if origen is not None:
        if not (origen / "tesseract.exe").exists():
            raise SystemExit(f"No se encontró tesseract.exe en {origen}")
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen / "tesseract.exe", destino / "tesseract.exe")
        for dll in origen.glob("*.dll"):
            shutil.copy2(dll, destino / dll.name)
        print(f"  copiados tesseract.exe y {len(list(origen.glob('*.dll')))} DLL")
    for idioma in IDIOMAS:
        descargar(TESSDATA_BEST.format(idioma), tessdata / f"{idioma}.traineddata")
    descargar(TESSDATA_OSD, tessdata / "osd.traineddata")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tesseract", type=Path, default=None, help="carpeta de una instalación de Tesseract (Windows)")
    ap.add_argument("--solo-modelos", action="store_true", help="solo modelos ONNX (pruebas en Linux)")
    args = ap.parse_args()
    if args.solo_modelos:
        modelos_rapidocr()
        modelo_tablas()
        return
    print("Modelos RapidOCR (medium):")
    modelos_rapidocr()
    print("Tablas (SLANet+):")
    modelo_tablas()
    print("Tesseract:")
    tesseract(args.tesseract)
    print("Listo.")


if __name__ == "__main__":
    sys.exit(main())
