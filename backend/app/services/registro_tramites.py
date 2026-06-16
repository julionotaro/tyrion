"""
Registro en memoria de trámites cargados manualmente.

Resuelve el problema de la sesión 11: los trámites creados vía carga manual
no aparecían en la Pantalla de Control. Este módulo es la fuente compartida
entre `app.api.carga` (escribe) y `app.api.control` (lee).

En esta etapa NO hay PostgreSQL disponible en el entorno de demo/cloud, por lo
que el registro vive en memoria del proceso. El contrato de cada trámite espeja
exactamente la forma de TRAMITES_PRUEBA, de modo que `GET /api/tramites` puede
combinar ambas fuentes sin distinguir el origen.

Cuando exista BD real, este módulo se reemplaza por RepositorioPostgres sin
tocar los endpoints (misma interfaz de lectura).
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timezone
from typing import Any

# Trámites creados por carga manual (forma idéntica a TRAMITES_PRUEBA)
_tramites: dict[str, dict[str, Any]] = {}

# Sesiones de carga abiertas: docs subidos antes de "procesar"
_sesiones: dict[str, dict[str, Any]] = {}

_lock = threading.Lock()


# ── Sesiones de carga ─────────────────────────────────────────────────────────

def crear_sesion(sesion_id: str) -> dict[str, Any]:
    """Inicia una sesión de carga vacía."""
    with _lock:
        sesion = {
            "sesion_id": sesion_id,
            "creada_at": datetime.now(timezone.utc).isoformat(),
            "documentos": [],        # list[dict] con clasificación + ruta
            "tramite_id": None,      # se rellena al procesar
        }
        _sesiones[sesion_id] = sesion
        return sesion


def obtener_sesion(sesion_id: str) -> dict[str, Any] | None:
    return _sesiones.get(sesion_id)


def agregar_documento_a_sesion(sesion_id: str, documento: dict[str, Any]) -> None:
    """Agrega un documento clasificado a la sesión. Crea la sesión si no existe."""
    with _lock:
        sesion = _sesiones.get(sesion_id)
        if sesion is None:
            sesion = {
                "sesion_id": sesion_id,
                "creada_at": datetime.now(timezone.utc).isoformat(),
                "documentos": [],
                "tramite_id": None,
            }
            _sesiones[sesion_id] = sesion
        sesion["documentos"].append(documento)


def marcar_sesion_procesada(sesion_id: str, tramite_id: str) -> None:
    with _lock:
        sesion = _sesiones.get(sesion_id)
        if sesion is not None:
            sesion["tramite_id"] = tramite_id


# ── Trámites ──────────────────────────────────────────────────────────────────

def agregar_tramite(tramite: dict[str, Any]) -> None:
    """Registra un trámite creado por carga manual."""
    with _lock:
        _tramites[tramite["id"]] = tramite


def listar_tramites() -> list[dict[str, Any]]:
    """Todos los trámites de carga manual, más recientes primero."""
    return list(_tramites.values())


def obtener_tramite(tramite_id: str) -> dict[str, Any] | None:
    return _tramites.get(tramite_id)


def contar_procesados_hoy() -> int:
    """Número de trámites creados hoy (UTC)."""
    hoy = date.today().isoformat()
    return sum(
        1 for t in _tramites.values()
        if str(t.get("fecha_entrada", "")).startswith(hoy)
    )


def ultima_actividad() -> str | None:
    """Timestamp ISO del trámite más reciente, o None si no hay ninguno."""
    if not _tramites:
        return None
    return max(str(t.get("fecha_entrada", "")) for t in _tramites.values())


def reset() -> None:
    """Limpia el registro — solo para tests."""
    with _lock:
        _tramites.clear()
        _sesiones.clear()
