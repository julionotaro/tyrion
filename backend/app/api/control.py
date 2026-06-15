"""
API de la Pantalla Control — endpoints REST para el dashboard operativo.

Los 6 macro-estados reflejan el ciclo de vida real de un trámite DGT:
  recibido → en_revision → pendiente_gestoria → listo_dgt → en_cadeteria → cerrado

Cuando USE_DATOS_PRUEBA=true (default en dev) usa datos hardcodeados.
Cuando hay BD real, los endpoints buscan en PostgreSQL (TODO sesión 5).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.datos_prueba import (
    ETIQUETAS_ESTADO,
    MACRO_ESTADOS,
    TRAMITES_PRUEBA,
)
from app.api.deps import get_usar_datos_prueba
from app.repositories.repositorio_postgres import RepositorioPostgres

router = APIRouter(prefix="/api", tags=["control"])


# ---------- schemas de respuesta ----------

class TramiteResumen(BaseModel):
    id: str
    tipo: str
    matricula: str | None
    bastidor: str | None
    gestoria: str
    estado: str
    estado_label: str
    fecha_entrada: str
    alerta: bool
    num_docs: int


class TramiteDetalle(BaseModel):
    id: str
    tipo: str
    matricula: str | None
    bastidor: str | None
    gestoria: str
    gestoria_email: str
    estado: str
    estado_label: str
    fecha_entrada: str
    alerta: bool
    num_comprobante_dgt: str | None = None
    documentos: list[dict[str, Any]]
    historial: list[dict[str, Any]]
    avisos_pendientes: list[dict[str, Any]]


class StatsResponse(BaseModel):
    conteos: dict[str, int]
    etiquetas: dict[str, str]
    total: int
    alertas: int


class EscalarResponse(BaseModel):
    tramite_id: str
    ok: bool
    mensaje: str


# ---------- helpers ----------

def _tramites_fuente(
    usar_prueba: bool,
    estado: str | None = None,
    gestoria: str | None = None,
    tipo: str | None = None,
) -> list[dict[str, Any]]:
    if usar_prueba:
        return TRAMITES_PRUEBA
    try:
        repo = RepositorioPostgres()
        return repo.listar_tramites(estado=estado, gestoria=gestoria, tipo=tipo)
    except Exception as exc:
        raise HTTPException(503, f"Error al consultar la base de datos: {exc}") from exc


def _a_resumen(t: dict[str, Any]) -> TramiteResumen:
    return TramiteResumen(
        id=t["id"],
        tipo=t["tipo"],
        matricula=t.get("matricula"),
        bastidor=t.get("bastidor"),
        gestoria=t["gestoria"],
        estado=t["estado"],
        estado_label=ETIQUETAS_ESTADO.get(t["estado"], t["estado"]),
        fecha_entrada=t["fecha_entrada"],
        alerta=t.get("alerta", False),
        num_docs=len(t.get("documentos", [])),
    )


# ---------- endpoints ----------

@router.get("/tramites", response_model=list[TramiteResumen])
def listar_tramites(
    estado: str | None = Query(None, description="Filtrar por macro-estado"),
    gestoria: str | None = Query(None, description="Filtrar por nombre de gestoría"),
    tipo: str | None = Query(None, description="TRANSFERENCIA | MATRICULACION | BAJA"),
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> list[TramiteResumen]:
    """Lista de trámites con filtros opcionales. Alimenta la tabla principal."""
    if usar_prueba:
        tramites = _tramites_fuente(usar_prueba)
        if estado:
            tramites = [t for t in tramites if t["estado"] == estado]
        if gestoria:
            tramites = [t for t in tramites
                        if gestoria.lower() in t["gestoria"].lower()]
        if tipo:
            tramites = [t for t in tramites if t["tipo"] == tipo.upper()]
    else:
        tramites = _tramites_fuente(usar_prueba, estado=estado, gestoria=gestoria, tipo=tipo)

    return [_a_resumen(t) for t in tramites]


@router.get("/tramites/{tramite_id}", response_model=TramiteDetalle)
def detalle_tramite(
    tramite_id: str,
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> TramiteDetalle:
    """Detalle completo de un trámite: documentos, historial, avisos."""
    if usar_prueba:
        tramites = _tramites_fuente(usar_prueba)
        tramite = next((t for t in tramites if t["id"] == tramite_id), None)
        if not tramite:
            raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")
        documentos = tramite.get("documentos", [])
        historial = tramite.get("historial", [])
        avisos_pendientes = tramite.get("avisos_pendientes", [])
        alerta = tramite.get("alerta", False)
    else:
        try:
            repo = RepositorioPostgres()
            tramite = repo.obtener_tramite(tramite_id)
            if not tramite:
                raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")
            documentos = repo.documentos_de_tramite(tramite_id)
            mensajes = repo.mensajes_de_tramite(tramite_id)
            historial = []
            avisos_pendientes = [
                {"tipo": m["tipo"], "asunto": m["asunto"], "preparado_at": str(m["preparado_at"])}
                for m in mensajes if not m.get("enviado_at")
            ]
            alerta = bool(avisos_pendientes)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, f"Error al consultar la base de datos: {exc}") from exc

    return TramiteDetalle(
        id=tramite["id"],
        tipo=tramite["tipo"],
        matricula=tramite.get("matricula"),
        bastidor=tramite.get("bastidor"),
        gestoria=tramite["gestoria"],
        gestoria_email=tramite.get("gestoria_email", ""),
        estado=tramite["estado"],
        estado_label=ETIQUETAS_ESTADO.get(tramite["estado"], tramite["estado"]),
        fecha_entrada=str(tramite.get("fecha_entrada", "")),
        alerta=alerta,
        num_comprobante_dgt=tramite.get("num_comprobante_dgt"),
        documentos=documentos,
        historial=historial,
        avisos_pendientes=avisos_pendientes,
    )


@router.get("/stats", response_model=StatsResponse)
def stats(
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> StatsResponse:
    """Conteos por macro-estado para los 6 cards superiores del dashboard."""
    tramites = _tramites_fuente(usar_prueba)
    conteos: dict[str, int] = {estado: 0 for estado in MACRO_ESTADOS}
    alertas = 0
    for t in tramites:
        estado = t.get("estado", "recibido")
        if estado in conteos:
            conteos[estado] += 1
        if t.get("alerta"):
            alertas += 1
    return StatsResponse(
        conteos=conteos,
        etiquetas=ETIQUETAS_ESTADO,
        total=len(tramites),
        alertas=alertas,
    )


@router.post("/tramites/{tramite_id}/escalar", response_model=EscalarResponse)
def escalar_tramite(
    tramite_id: str,
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> EscalarResponse:
    """Escala manualmente un trámite al administrativo.

    Solo disponible cuando estado = pendiente_gestoria.
    En producción actualiza la BD y crea un MensajeSaliente tipo ESCALADO.
    TODO sesión 5: persistir en PostgreSQL + disparar mensaje real.
    """
    tramites = _tramites_fuente(usar_prueba)
    tramite = next((t for t in tramites if t["id"] == tramite_id), None)
    if not tramite:
        raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")
    if tramite["estado"] != "pendiente_gestoria":
        raise HTTPException(
            400,
            f"Solo se puede escalar desde pendiente_gestoria "
            f"(estado actual: {tramite['estado']}).",
        )
    # En modo prueba simulamos el escalado en memoria
    tramite["alerta"] = True
    tramite["historial"].append({
        "momento": "ahora",
        "evento": "Escalado manual al administrativo",
        "actor": "admin_web",
    })
    return EscalarResponse(
        tramite_id=tramite_id,
        ok=True,
        mensaje="Trámite escalado al administrativo. Mensaje PREPARADO.",
    )
