"""
Dependencias compartidas de la API FastAPI.

Proporciona la sesión de BD y el flag de datos de prueba.
En v1 sin BD real: USE_DATOS_PRUEBA=true devuelve los datos hardcodeados.
"""
from __future__ import annotations

from app.core.config import get_settings


def get_usar_datos_prueba() -> bool:
    return get_settings().use_datos_prueba
