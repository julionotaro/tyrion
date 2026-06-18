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
from app.core.config import get_settings

from app.api.datos_prueba import (
    ETIQUETAS_ESTADO,
    MACRO_ESTADOS,
    TRAMITES_PRUEBA,
    PLANILLA_DIA_PRUEBA,
    planilla_prueba_como_objeto,
)
from app.api.deps import get_usar_datos_prueba
from app.repositories.repositorio_postgres import RepositorioPostgres
from app.services import registro_tramites
from app.services.ingesta_planilla import (
    parse_relacion_transmisiones,
    parse_relacion_matriculas,
    TipoPlanilla,
)

router = APIRouter(prefix="/api", tags=["control"])


# ---------- schemas de respuesta ----------

class TramiteResumen(BaseModel):
    id: str
    tipo: str
    subtipo: str | None = None
    matricula: str | None
    bastidor: str | None
    gestoria: str
    estado: str
    estado_label: str
    fecha_entrada: str
    alerta: bool
    num_docs: int
    asunto_email: str | None = None
    documentos_faltantes: list[str] = []
    avisos_pendientes: list[dict] = []


class TramiteDetalle(BaseModel):
    id: str
    tipo: str
    subtipo: str | None = None
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
    verificaciones: list[dict[str, Any]] = []


class StatsResponse(BaseModel):
    conteos: dict[str, int]
    etiquetas: dict[str, str]
    total: int
    alertas: int
    total_planificados: int = 0
    sin_match: int = 0
    pendiente_jefatura: int = 0
    sin_documentacion: int = 0


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
    """Fuente combinada de trámites: base (prueba o BD) + carga manual.

    Los trámites creados vía carga manual (registro_tramites) SIEMPRE se incluyen,
    de modo que aparezcan en la Pantalla de Control junto a los demás.
    """
    manuales = registro_tramites.listar_tramites()
    if usar_prueba:
        # Más recientes (carga manual) primero
        return manuales + list(TRAMITES_PRUEBA)
    try:
        repo = RepositorioPostgres()
        base = repo.listar_tramites(estado=estado, gestoria=gestoria, tipo=tipo)
        return manuales + base
    except Exception as exc:
        raise HTTPException(503, f"Error al consultar la base de datos: {exc}") from exc


def _a_resumen(t: dict[str, Any]) -> TramiteResumen:
    return TramiteResumen(
        id=t["id"],
        tipo=t["tipo"],
        subtipo=t.get("subtipo"),
        matricula=t.get("matricula"),
        bastidor=t.get("bastidor"),
        gestoria=t["gestoria"],
        estado=t["estado"],
        estado_label=ETIQUETAS_ESTADO.get(t["estado"], t["estado"]),
        fecha_entrada=t["fecha_entrada"],
        alerta=t.get("alerta", False),
        num_docs=len(t.get("documentos", [])),
        asunto_email=t.get("asunto_email"),
        documentos_faltantes=t.get("documentos_faltantes", []),
        avisos_pendientes=t.get("avisos_pendientes", []),
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
    # Trámites de carga manual viven en el registro en memoria (cualquier modo)
    manual = registro_tramites.obtener_tramite(tramite_id)
    if manual is not None:
        return TramiteDetalle(
            id=manual["id"],
            tipo=manual["tipo"],
            subtipo=manual.get("subtipo"),
            matricula=manual.get("matricula"),
            bastidor=manual.get("bastidor"),
            gestoria=manual["gestoria"],
            gestoria_email=manual.get("gestoria_email", ""),
            estado=manual["estado"],
            estado_label=ETIQUETAS_ESTADO.get(manual["estado"], manual["estado"]),
            fecha_entrada=str(manual.get("fecha_entrada", "")),
            alerta=manual.get("alerta", False),
            num_comprobante_dgt=manual.get("num_comprobante_dgt"),
            documentos=manual.get("documentos", []),
            historial=manual.get("historial", []),
            avisos_pendientes=manual.get("avisos_pendientes", []),
            verificaciones=manual.get("verificaciones", []),
        )

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
        subtipo=tramite.get("subtipo"),
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
        verificaciones=tramite.get("verificaciones", []),
    )


@router.get("/stats", response_model=StatsResponse)
def stats(
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> StatsResponse:
    """Conteos por macro-estado + métricas de planilla para los cards del dashboard."""
    tramites = _tramites_fuente(usar_prueba)
    conteos: dict[str, int] = {estado: 0 for estado in MACRO_ESTADOS}
    alertas = 0
    pendiente_jefatura = 0
    for t in tramites:
        estado = t.get("estado", "recibido")
        if estado in conteos:
            conteos[estado] += 1
        elif estado == "pendiente_jefatura":
            pendiente_jefatura += 1
        if t.get("alerta"):
            alertas += 1

    # Métricas de planilla
    if usar_prueba:
        planilla = PLANILLA_DIA_PRUEBA
        total_planificados = len(planilla.get("tramites_planificados", []))
        sin_documentacion = sum(
            1 for tp in planilla.get("tramites_planificados", [])
            if tp.get("estado") == "sin_documentacion"
        )
        sin_match = len(planilla.get("emails_sin_match", []))
    else:
        total_planificados = 0
        sin_documentacion = 0
        sin_match = 0

    return StatsResponse(
        conteos=conteos,
        etiquetas=ETIQUETAS_ESTADO,
        total=len(tramites),
        alertas=alertas,
        total_planificados=total_planificados,
        sin_match=sin_match,
        pendiente_jefatura=pendiente_jefatura,
        sin_documentacion=sin_documentacion,
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


# ── Endpoints de planilla ─────────────────────────────────────────────────────

class PlanillaCargarRequest(BaseModel):
    contenido: str
    tipo: str   # "TRANSMISIONES" | "MATRICULAS"
    fuente: str = "manual"


class PlanillaCargarResponse(BaseModel):
    ok: bool
    tipo: str
    filas_parseadas: int
    mensaje: str


class PlanillaHoyResponse(BaseModel):
    fecha: str
    tipo: str
    total_planificados: int
    sin_documentacion: int
    con_documentacion: int
    validados: int
    escalados: int


class SinMatchResponse(BaseModel):
    emails_sin_match: list[dict[str, Any]]
    total: int


@router.post("/planilla", response_model=PlanillaCargarResponse)
def cargar_planilla(
    payload: PlanillaCargarRequest,
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> PlanillaCargarResponse:
    """Carga la planilla del día (texto plano CSV exportado de Tempus).

    En modo prueba: parsea y devuelve el conteo sin persistir.
    En modo BD real: persiste en tabla planilla_dia + tramite_planificado.
    """
    tipo_upper = payload.tipo.upper()
    try:
        if tipo_upper == TipoPlanilla.TRANSMISIONES.value:
            planilla = parse_relacion_transmisiones(payload.contenido, fuente=payload.fuente)
        elif tipo_upper == TipoPlanilla.MATRICULAS.value:
            planilla = parse_relacion_matriculas(payload.contenido, fuente=payload.fuente)
        else:
            raise HTTPException(400, f"Tipo de planilla desconocido: '{payload.tipo}'. "
                                "Usar TRANSMISIONES o MATRICULAS.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Error parseando planilla: {exc}") from exc

    if not usar_prueba:
        try:
            repo = RepositorioPostgres()
            planilla_id = repo.guardar_planilla_dia(planilla)
            for tp in planilla.tramites:
                repo.guardar_tramite_planificado(tp, planilla_id)
        except Exception as exc:
            raise HTTPException(503, f"Error persistiendo planilla: {exc}") from exc

    return PlanillaCargarResponse(
        ok=True,
        tipo=tipo_upper,
        filas_parseadas=len(planilla.tramites),
        mensaje=f"Planilla {tipo_upper} cargada: {len(planilla.tramites)} trámites planificados.",
    )


@router.get("/planilla/hoy", response_model=PlanillaHoyResponse)
def planilla_hoy(
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> PlanillaHoyResponse:
    """Estado de la planilla del día: cuántos trámites tienen/no tienen documentación."""
    if usar_prueba:
        tps = PLANILLA_DIA_PRUEBA.get("tramites_planificados", [])
        return PlanillaHoyResponse(
            fecha=PLANILLA_DIA_PRUEBA["fecha"],
            tipo=PLANILLA_DIA_PRUEBA["tipo"],
            total_planificados=len(tps),
            sin_documentacion=sum(1 for t in tps if t["estado"] == "sin_documentacion"),
            con_documentacion=sum(1 for t in tps if t["estado"] == "con_documentacion"),
            validados=sum(1 for t in tps if t["estado"] == "validado"),
            escalados=sum(1 for t in tps if t["estado"] == "escalado"),
        )
    # BD real: pendiente implementación completa
    raise HTTPException(503, "Planilla desde BD real: pendiente sesión 8.")


@router.get("/planilla/sin-match", response_model=SinMatchResponse)
def planilla_sin_match(
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> SinMatchResponse:
    """Emails recibidos hoy sin fila correspondiente en la planilla."""
    if usar_prueba:
        sin_match = PLANILLA_DIA_PRUEBA.get("emails_sin_match", [])
        return SinMatchResponse(emails_sin_match=sin_match, total=len(sin_match))
    try:
        repo = RepositorioPostgres()
        sin_match = repo.listar_tramites_sin_match_hoy()
        return SinMatchResponse(emails_sin_match=sin_match, total=len(sin_match))
    except Exception as exc:
        raise HTTPException(503, f"Error consultando sin_match: {exc}") from exc


# ── Salud del sistema ─────────────────────────────────────────────────────────

class SaludResponse(BaseModel):
    activo: bool
    clasificador: str   # "anthropic" | "openai" | "mock"
    modelo: str
    procesados_hoy: int
    ultima_actividad: str | None


@router.get("/salud", response_model=SaludResponse)
def salud_sistema() -> SaludResponse:
    """Estado del sistema: clasificador activo, modelo en uso, actividad reciente."""
    from datetime import datetime, timezone
    s = get_settings()

    if s.openai_api_key:
        clasificador = "openai"
        modelo = s.clasificador_openai_model
    elif s.anthropic_api_key:
        clasificador = "anthropic"
        modelo = s.clasificador_model
    else:
        clasificador = "mock"
        modelo = "mock"

    procesados_hoy = registro_tramites.contar_procesados_hoy()
    ultima = registro_tramites.ultima_actividad()

    return SaludResponse(
        activo=True,
        clasificador=clasificador,
        modelo=modelo,
        procesados_hoy=procesados_hoy,
        ultima_actividad=ultima or datetime.now(timezone.utc).isoformat(),
    )
