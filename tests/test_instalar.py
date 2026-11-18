"""Instalador sobre Python: búsqueda y copia de recursos, y comando del acceso directo."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("instalar", RAIZ / "instalar.py")
instalar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(instalar)


def _zip_falso(base: Path) -> Path:
    r = base / "eh-ocr" / "_internal" / "recursos"
    (r / "modelos" / "rapidocr").mkdir(parents=True)
    (r / "modelos" / "rapidocr" / "PP-OCRv6_det_medium.onnx").write_bytes(b"m")
    (r / "tesseract" / "tessdata").mkdir(parents=True)
    (r / "tesseract" / "tesseract.exe").write_bytes(b"t")
    return base / "eh-ocr"


def test_busca_y_copia_recursos_del_zip(tmp_path):
    origen = instalar.buscar_recursos(_zip_falso(tmp_path))
    destino = tmp_path / "repo" / "recursos"
    assert instalar.copiar_recursos(origen, destino) == ["modelos", "tesseract"]
    assert (destino / "modelos" / "rapidocr" / "PP-OCRv6_det_medium.onnx").exists()
    assert (destino / "tesseract" / "tesseract.exe").exists()


def test_carpeta_equivocada_da_mensaje_claro(tmp_path):
    with pytest.raises(SystemExit, match="No encontré los recursos"):
        instalar.buscar_recursos(tmp_path)


def test_acceso_directo_escapa_comillas():
    cmd = instalar.comando_acceso_directo(
        Path(r"C:\Users\o'neil\Desktop\eh-ocr.lnk"), Path(r"C:\Py\pythonw.exe"), "-m eh_ocr",
        Path(r"D:\PST\eh-ocr"), Path(r"D:\PST\eh-ocr\recursos\eh-ocr.ico"),
    )
    assert cmd[:4] == ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
    assert "o''neil" in cmd[4]  # comilla simple escapada: sin inyección en PowerShell
    assert "$s.Arguments='-m eh_ocr'" in cmd[4]


def test_instala_lo_que_encuentra_y_avisa_lo_que_falta(tmp_path, capsys):
    r = tmp_path / "eh-ocr" / "_internal" / "recursos" / "tesseract"
    r.mkdir(parents=True)
    origen = instalar.buscar_recursos(tmp_path / "eh-ocr")
    assert instalar.copiar_recursos(origen, tmp_path / "repo") == ["tesseract"]
    assert "Falta «modelos»" in capsys.readouterr().out


def test_acepta_la_carpeta_superior(tmp_path):
    _zip_falso(tmp_path)  # tmp_path/eh-ocr/_internal/recursos
    assert instalar.buscar_recursos(tmp_path).name == "recursos"
