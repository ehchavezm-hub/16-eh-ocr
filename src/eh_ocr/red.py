"""Bloqueo total de red.

eh-ocr es absolutamente autónomo: ningún componente (ni librerías de
terceros que intenten descargar modelos) puede abrir una conexión.
"""

from __future__ import annotations

import socket


class RedBloqueadaError(OSError):
    """Se intentó una conexión de red, prohibida en eh-ocr."""


_bloqueada = False
_originales: dict[str, object] = {}


def _prohibido(*_args, **_kwargs):
    raise RedBloqueadaError("eh-ocr funciona sin internet: conexión de red bloqueada.")


def bloquear_red() -> None:
    """Impide cualquier conexión saliente desde este proceso."""
    global _bloqueada
    if _bloqueada:
        return
    _originales["connect"] = socket.socket.connect
    _originales["connect_ex"] = socket.socket.connect_ex
    _originales["create_connection"] = socket.create_connection
    _originales["getaddrinfo"] = socket.getaddrinfo
    socket.socket.connect = _prohibido  # type: ignore[method-assign]
    socket.socket.connect_ex = _prohibido  # type: ignore[method-assign]
    socket.create_connection = _prohibido  # type: ignore[assignment]
    socket.getaddrinfo = _prohibido  # type: ignore[assignment]
    _bloqueada = True


def desbloquear_red() -> None:
    """Solo para pruebas."""
    global _bloqueada
    if not _bloqueada:
        return
    socket.socket.connect = _originales["connect"]  # type: ignore[method-assign]
    socket.socket.connect_ex = _originales["connect_ex"]  # type: ignore[method-assign]
    socket.create_connection = _originales["create_connection"]  # type: ignore[assignment]
    socket.getaddrinfo = _originales["getaddrinfo"]  # type: ignore[assignment]
    _bloqueada = False


def red_bloqueada() -> bool:
    return _bloqueada
