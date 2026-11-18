"""Detección del equipo para ajustar el paralelismo y el acelerador."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Equipo:
    nucleos: int
    ram_gb: float
    acelerador: str          # "DirectML" o "CPU"
    proveedores: tuple[str, ...]

    @property
    def paginas_en_paralelo(self) -> int:
        # Cada página usa varios hilos internos (ONNX Runtime + Tesseract).
        por_nucleos = max(1, self.nucleos // 4)
        por_ram = max(1, int(self.ram_gb // 4))
        return max(1, min(4, por_nucleos, por_ram))

    @property
    def descripcion(self) -> str:
        return f"{self.nucleos} núcleos · {self.ram_gb:.0f} GB RAM"


def _ram_gb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return st.ullTotalPhys / 1024**3
        with open("/proc/meminfo", encoding="ascii") as f:
            for linea in f:
                if linea.startswith("MemTotal:"):
                    return int(linea.split()[1]) / 1024**2
    except Exception:
        pass
    return 8.0


@lru_cache(maxsize=1)
def detectar() -> Equipo:
    try:
        import onnxruntime as ort

        proveedores = tuple(ort.get_available_providers())
    except Exception:
        proveedores = ("CPUExecutionProvider",)
    acelerador = "DirectML" if "DmlExecutionProvider" in proveedores else "CPU"
    if os.environ.get("EH_OCR_SOLO_CPU") == "1":  # también lo activa la protección contra caídas
        acelerador = "CPU"
    return Equipo(
        nucleos=os.cpu_count() or 4,
        ram_gb=_ram_gb(),
        acelerador=acelerador,
        proveedores=proveedores,
    )
