"""
Almacenamiento compartido en memoria para documentos cargados via /api/carga.

SESIONES_CARGA: sesiones de carga activas (carga.py escribe, carga.py lee).
DOCUMENTOS_CARGA: documentos procesados con extracción detallada.
             (carga.py escribe durante procesar_sesion; documentos.py lee).
"""
from __future__ import annotations

SESIONES_CARGA: dict = {}
DOCUMENTOS_CARGA: dict = {}


def reset() -> None:
    """Solo para tests."""
    SESIONES_CARGA.clear()
    DOCUMENTOS_CARGA.clear()
