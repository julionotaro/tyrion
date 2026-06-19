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

import re
import threading
from datetime import date, datetime, timezone
from typing import Any

# Patrones para correlación por asunto
_PAT_MATRICULA = re.compile(r'\b(\d{4})\s?([A-Z]{3})\b')
_PAT_BASTIDOR = re.compile(r'\b([A-HJ-NPR-Z0-9]{17})\b')

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


_ESTADOS_ABIERTOS: frozenset[str] = frozenset({"pendiente_gestoria", "en_revision"})


# ── Normalización de identificadores ─────────────────────────────────────────

def normalizar_matricula(m: str | None) -> str:
    """Normaliza para comparación: sin espacios, sin guiones, mayúsculas."""
    if not m:
        return ""
    return m.replace(" ", "").replace("-", "").upper()


def normalizar_bastidor(b: str | None) -> str:
    """Normaliza bastidor/VIN para comparación: sin espacios, mayúsculas."""
    if not b:
        return ""
    return b.replace(" ", "").replace("-", "").upper()


# ── Búsqueda ──────────────────────────────────────────────────────────────────

def buscar_tramite_existente(
    matricula: str | None = None,
    bastidor: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    asunto: str | None = None,
) -> dict[str, Any] | None:
    """Busca trámite abierto por headers email (capa 1) o matrícula/bastidor (capa 2).

    Capa 2 cruza por matrícula O bastidor en un único recorrido: si el trámite
    existente tiene matrícula y el nuevo documento trae bastidor (o viceversa),
    también correlaciona.
    Estados considerados abiertos: pendiente_gestoria, en_revision.
    """
    # Capa 1: headers email → message_ids_avisos
    ref_ids: set[str] = set()
    if in_reply_to:
        ref_ids.add(in_reply_to.strip())
    if references:
        for rid in references.split():
            ref_ids.add(rid.strip())
    ref_ids.discard("")
    if ref_ids:
        for tramite in _tramites.values():
            ids_avisos = set(tramite.get("message_ids_avisos") or [])
            if ids_avisos & ref_ids:
                return tramite

    # Capa 2: matrícula y/o bastidor en un único recorrido
    mat_norm = normalizar_matricula(matricula)
    bas_norm = normalizar_bastidor(bastidor)

    if mat_norm or bas_norm:
        for tramite in _tramites.values():
            if tramite.get("estado") not in _ESTADOS_ABIERTOS:
                continue
            if mat_norm:
                t_mat = normalizar_matricula(tramite.get("matricula"))
                if t_mat and t_mat == mat_norm:
                    return tramite
            if bas_norm:
                t_bas = normalizar_bastidor(tramite.get("bastidor"))
                if t_bas and t_bas == bas_norm:
                    return tramite

    # Capa 2 por asunto (solo si no vinieron mat/bas directos)
    if asunto and not mat_norm and not bas_norm:
        mat_m = _PAT_MATRICULA.search(asunto.upper())
        if mat_m:
            mat_from_asunto = normalizar_matricula(mat_m.group(1) + mat_m.group(2))
            for tramite in _tramites.values():
                if tramite.get("estado") not in _ESTADOS_ABIERTOS:
                    continue
                if normalizar_matricula(tramite.get("matricula")) == mat_from_asunto:
                    return tramite
        bas_m = _PAT_BASTIDOR.search(asunto.upper())
        if bas_m:
            bas_from_asunto = normalizar_bastidor(bas_m.group(1))
            for tramite in _tramites.values():
                if tramite.get("estado") not in _ESTADOS_ABIERTOS:
                    continue
                if normalizar_bastidor(tramite.get("bastidor")) == bas_from_asunto:
                    return tramite

    return None


def buscar_tramite_para_respuesta(email) -> dict[str, Any] | None:
    """Correlaciona email entrante con trámite abierto. Delega a buscar_tramite_existente."""
    return buscar_tramite_existente(
        in_reply_to=getattr(email, "in_reply_to", "") or None,
        references=getattr(email, "references", "") or None,
        asunto=getattr(email, "asunto", "") or None,
    )


def reset() -> None:
    """Limpia el registro — solo para tests."""
    with _lock:
        _tramites.clear()
        _sesiones.clear()
