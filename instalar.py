"""Instalador de eh-ocr sobre Python (para equipos que bloquean .exe sin firma digital).

Se ejecuta UNA vez, desde la carpeta del repositorio:

    py -3.13 instalar.py "D:\\PST\\x"

donde "D:\\PST\\x" es la carpeta descomprimida del ZIP de eh-ocr (la que tiene eh-ocr.exe y
_internal). De ahí se copian los modelos precisos y Tesseract: no se descarga nada más.

Pasos:
  1. Verifica Python 3.13 o superior.
  2. Instala eh-ocr y sus librerías (las de tablas, sin dependencias).
  3. Copia modelos y Tesseract del ZIP a recursos\\.
  4. Prueba eh-ocr sin internet (autoprueba).
  5. Crea los accesos directos «eh-ocr» (Escritorio) y «Abrir eh-ocr» (esta carpeta),
     que se abren sin ventana negra.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RECURSOS = RAIZ / "recursos"
PARTES = ("modelos", "tesseract")  # lo que se toma del paquete; fuentes e ícono ya vienen en el repo


def paso(n: int, texto: str) -> None:
    print(f"\n[{n}/5] {texto}")


def buscar_recursos(origen: Path) -> Path:
    """Acepta la carpeta del ZIP (con _internal), su carpeta recursos o la carpeta superior."""
    candidatas = [origen / "_internal" / "recursos", origen / "recursos", origen]
    candidatas += [p / "_internal" / "recursos" for p in origen.glob("*") if p.is_dir()]
    for candidata in candidatas:
        if any((candidata / parte).is_dir() for parte in PARTES):
            return candidata
    detalle = ""
    if origen.is_dir():
        contenido = ", ".join(sorted(p.name for p in origen.iterdir())[:15]) or "(vacía)"
        detalle = f"\nContenido de esa carpeta: {contenido}"
    raise SystemExit(
        f"No encontré los recursos en «{origen}».{detalle}\n"
        "Indica la carpeta descomprimida del ZIP de eh-ocr (la que contiene eh-ocr.exe y _internal)."
    )


def copiar_recursos(origen: Path, destino: Path = RECURSOS) -> list[str]:
    """Copia lo que encuentre; avisa de lo que falte (eh-ocr funciona igual, con menos precisión)."""
    copiados = []
    for parte in PARTES:
        if not (origen / parte).is_dir():
            print(f"  ⚠ Falta «{parte}» en {origen}: se instala sin esa parte.")
            continue
        d = destino / parte
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(origen / parte, d)
        copiados.append(parte)
    return copiados


def pythonw() -> Path:
    exe = Path(sys.executable)
    candidato = exe.with_name("pythonw.exe")
    return candidato if candidato.exists() else exe


def comando_acceso_directo(destino_lnk: Path, objetivo: Path, argumentos: str, carpeta: Path, icono: Path) -> list[str]:
    """Comando de PowerShell que crea el acceso directo (comillas simples escapadas)."""

    def ps(valor: object) -> str:
        return "'" + str(valor).replace("'", "''") + "'"

    script = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({ps(destino_lnk)});"
        f"$s.TargetPath={ps(objetivo)};"
        f"$s.Arguments={ps(argumentos)};"
        f"$s.WorkingDirectory={ps(carpeta)};"
        f"$s.IconLocation={ps(icono)};"
        "$s.Description='eh-ocr: OCR autónomo';"
        "$s.Save()"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]


def escritorio() -> Path:
    try:
        salida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if salida:
            return Path(salida)
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def main() -> int:
    print("eh-ocr — instalación sobre Python")
    if len(sys.argv) >= 2:
        origen = Path(sys.argv[1].strip().strip('"'))
    else:
        origen = Path(input(
            "Arrastra aquí la carpeta descomprimida del ZIP de eh-ocr y pulsa Enter:\n> "
        ).strip().strip('"'))

    paso(1, "Verificando Python")
    if sys.version_info < (3, 13):
        raise SystemExit(f"Se necesita Python 3.13 o superior (tienes {sys.version.split()[0]}). Usa: py -3.13 instalar.py")
    print(f"  Python {sys.version.split()[0]} ✓")
    recursos_zip = buscar_recursos(origen)

    paso(2, "Instalando eh-ocr y sus librerías (puede tardar unos minutos)")
    pip = [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check"]
    subprocess.run([*pip, "-e", str(RAIZ)], check=True)
    subprocess.run([*pip, "--no-deps", "-r", str(RAIZ / "desarrollo" / "requirements-tablas.txt")], check=True)
    print("  Librerías instaladas ✓")

    paso(3, "Copiando modelos precisos y Tesseract desde el ZIP")
    print(f"  Recursos encontrados en {recursos_zip}")
    copiados = copiar_recursos(recursos_zip)
    print(f"  Copiado ({', '.join(copiados) or 'nada'}) a {RECURSOS} ✓")

    paso(4, "Probando eh-ocr sin internet")
    with tempfile.TemporaryDirectory() as tmp:
        informe = Path(tmp) / "autoprueba.txt"
        entorno = dict(os.environ, EH_OCR_DATOS=str(Path(tmp) / "datos"))
        r = subprocess.run([sys.executable, "-m", "eh_ocr", "--autoprueba", str(informe)], env=entorno)
        texto = informe.read_text(encoding="utf-8") if informe.exists() else "(sin informe)"
    print("  " + texto.splitlines()[0] if texto else "")
    if r.returncode != 0:
        print("  ⚠ La autoprueba no salió bien. eh-ocr se instaló igual; envía este mensaje para revisarlo.")

    paso(5, "Creando el acceso directo en el Escritorio")
    if os.name != "nt":
        print("  (solo en Windows)")
        return 0
    for lnk in (escritorio() / "eh-ocr.lnk", RAIZ / "Abrir eh-ocr.lnk"):
        subprocess.run(
            comando_acceso_directo(lnk, pythonw(), "-m eh_ocr", RAIZ, RECURSOS / "eh-ocr.ico"), check=True
        )
        print(f"  {lnk} ✓")
    print("\nListo. Abre eh-ocr con doble clic en «eh-ocr» del Escritorio o en «Abrir eh-ocr» de esta carpeta.")
    print("No uses eh-ocr.exe en este equipo: la política de la empresa lo bloquea.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
