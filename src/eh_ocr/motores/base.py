"""Interfaz común de los motores de OCR."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..modelo import Palabra


class MotorNoDisponible(RuntimeError):
    """El motor no está incluido o no pudo iniciarse en este equipo."""


class Motor(ABC):
    nombre: str = "motor"

    @abstractmethod
    def disponible(self) -> bool:
        """True si el motor puede usarse en este equipo."""

    @abstractmethod
    def reconocer(self, imagen: np.ndarray) -> list[Palabra]:
        """Reconoce palabras en una imagen RGB. Cajas en píxeles de esa imagen."""
