"""Falla si alguna dependencia instalada tiene licencia GPL/AGPL o no comercial.

LGPL se admite (solo PySide6/shiboken6, enlazados dinámicamente y sin modificar).
"""

from __future__ import annotations

import re
import sys
from importlib.metadata import PackageNotFoundError, distribution, distributions

PROHIBIDAS = re.compile(r"\b(A?GPL|GNU (Affero )?General Public|Non-?Commercial|CC-BY-NC)\b", re.I)
# Paquetes con licencia múltiple donde se usa la opción permitida
EXCEPCIONES = {
    "pyside6": "LGPL-3.0 (opción elegida de la licencia múltiple de Qt for Python)",
    "pyside6-essentials": "LGPL-3.0",
    "pyside6-addons": "LGPL-3.0",
    "shiboken6": "LGPL-3.0",
    "pyinstaller": "GPL con excepción de empaquetado: no forma parte de eh-ocr",
    "pyinstaller-hooks-contrib": "GPL/Apache: solo herramienta de construcción",
}
# Herramientas de desarrollo que no se distribuyen
SOLO_DESARROLLO = {"pytest", "pluggy", "iniconfig", "pip", "setuptools", "wheel", "altgraph", "pefile", "pywin32-ctypes"}


def licencia(dist) -> str:
    md = dist.metadata
    partes = [md.get("License-Expression") or "", md.get("License") or ""]
    partes += [c for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    return " | ".join(p.strip().splitlines()[0] for p in partes if p and p.strip())


def dependencias(raiz: str = "eh-ocr") -> list:
    """Cierre de dependencias de eh-ocr que se distribuyen (sin extras de desarrollo)."""
    from packaging.requirements import Requirement

    vistos: dict[str, object] = {}
    pila = [raiz, "rapid-table", "rapid-layout"]  # instaladas aparte (requirements-tablas.txt)
    while pila:
        nombre = pila.pop().lower().replace("_", "-")
        if nombre in vistos:
            continue
        try:
            d = distribution(nombre)
        except PackageNotFoundError:
            continue
        vistos[nombre] = d
        for req in d.requires or []:
            r = Requirement(req)
            if r.marker is not None and not r.marker.evaluate({"extra": ""}):
                continue
            pila.append(r.name)
    vistos.pop(raiz, None)
    return list(vistos.values())


def main() -> int:
    problemas = []
    filas = []
    todas = "--todas" in sys.argv
    lista = list(distributions()) if todas else dependencias()
    if not lista:
        print("eh-ocr no está instalado (pip install -e .); se revisan todas las dependencias.")
        lista = list(distributions())
    for d in sorted(lista, key=lambda d: d.metadata["Name"].lower()):
        nombre = d.metadata["Name"].lower().replace("_", "-")
        lic = licencia(d)
        filas.append(f"{d.metadata['Name']} {d.version}: {lic or '(sin dato)'}")
        if nombre in EXCEPCIONES or nombre in SOLO_DESARROLLO or nombre.startswith("pyside6"):
            continue
        # Licencia múltiple que ofrece LGPL (p. ej. "LGPL-3.0-only OR GPL-3.0-only"): se usa LGPL
        if " OR " in lic and re.search(r"\bLGPL", lic):
            continue
        sin_lgpl = re.sub(r"\bL(esser )?GPL[\w.-]*|GNU Lesser General Public[^|]*", "", lic, flags=re.I)
        if PROHIBIDAS.search(sin_lgpl):
            problemas.append(f"{d.metadata['Name']} {d.version}: {lic}")
    print("\n".join(filas))
    if problemas:
        print("\nLICENCIAS PROHIBIDAS:\n  " + "\n  ".join(problemas))
        return 1
    print("\nOK: ninguna dependencia con licencia GPL/AGPL/no comercial.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
