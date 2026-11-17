"""Motores de reconocimiento. Todos implementan la interfaz `Motor`."""

from .base import Motor, MotorNoDisponible

__all__ = ["Motor", "MotorNoDisponible"]
