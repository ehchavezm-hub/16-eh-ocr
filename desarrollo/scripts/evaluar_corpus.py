"""Mide la precisión de eh-ocr con tus documentos reales.

Prepara la carpeta corpus/ (nunca se sube a git):

    corpus/
      contrato.pdf
      contrato.correcto.txt      <- texto exacto, revisado por ti
      factura.jpg
      factura.correcto.txt

Para crear el .correcto.txt de forma asistida:
    python desarrollo/scripts/evaluar_corpus.py --borradores
genera <nombre>.borrador.txt con el mejor resultado de eh-ocr; corrígelo a mano y
guárdalo como <nombre>.correcto.txt.

Luego:
    python desarrollo/scripts/evaluar_corpus.py
muestra el error por documento (CER/WER) y si cumple las metas
(< 1 % en escaneos limpios, < 5 % en fotos).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from eh_ocr.documento import EXT_ADMITIDAS  # noqa: E402
from eh_ocr.metricas import cer, wer  # noqa: E402
from eh_ocr.modelo import TipoPagina  # noqa: E402
from eh_ocr.pipeline import procesar_documento  # noqa: E402
from eh_ocr.red import bloquear_red  # noqa: E402

META = {TipoPagina.ESCANEO: 0.01, TipoPagina.FOTO: 0.05, TipoPagina.DIGITAL: 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=RAIZ / "corpus")
    ap.add_argument("--borradores", action="store_true")
    args = ap.parse_args()
    bloquear_red()
    docs = sorted(p for p in args.corpus.iterdir() if p.suffix.lower() in EXT_ADMITIDAS)
    if not docs:
        print(f"No hay documentos en {args.corpus}")
        return 1
    fallos = 0
    print(f"{'Documento':40} {'Tipo':9} {'CER':>7} {'WER':>7}  Meta")
    for doc in docs:
        r = procesar_documento(doc)
        if args.borradores:
            destino = doc.with_name(doc.stem + ".borrador.txt")
            destino.write_text(r.texto, encoding="utf-8")
            print(f"borrador: {destino.name}")
            continue
        ref = doc.with_name(doc.stem + ".correcto.txt")
        if not ref.exists():
            print(f"{doc.name:40} (sin {ref.name})")
            continue
        tipo = max((p.perfil.tipo for p in r.paginas), key=lambda t: META[t])
        c, w = cer(ref.read_text(encoding="utf-8"), r.texto), wer(ref.read_text(encoding="utf-8"), r.texto)
        ok = c <= META[tipo] or (tipo == TipoPagina.DIGITAL and c < 0.001)
        fallos += not ok
        print(f"{doc.name[:40]:40} {tipo.value:9} {c * 100:6.2f}% {w * 100:6.2f}%  {'✓' if ok else '✗'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
