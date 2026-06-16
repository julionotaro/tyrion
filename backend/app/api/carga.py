"""
API de carga manual de documentos.

La carga manual es la vía real para documentación en papel digitalizada:
60% de las gestorías entrega en papel, el administrativo escanea y carga aquí.

Flujo:
  1. POST /api/carga/tramite  → crea un tramite_id
  2. POST /api/carga/tramite/{id}/documento  → sube archivo, dispara clasificación
     + cotejo automático, devuelve resultado por documento
  3. GET  /api/carga/tramite/{id}/resultado  → estado final del checklist
"""
from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.catalogo_documental import TipoTramite
from app.services.clasificador import ClasificadorDocumental
from app.services.motor_cotejo import MotorCotejo, EstadoChecklist
from app.services.storage import guardar_archivo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/carga", tags=["carga"])

# Almacenamiento en memoria de trámites cargados manualmente en esta sesión.
# En producción usaría RepositorioPostgres; aquí vale para la demo.
_tramites_manuales: dict[str, dict[str, Any]] = {}

_clf = ClasificadorDocumental()
_motor = MotorCotejo()

TIPO_TRAMITE_MAP: dict[str, TipoTramite] = {
    "transferencia": TipoTramite.TRANSFERENCIA,
    "matriculacion": TipoTramite.MATRICULACION,
    "baja": TipoTramite.BAJA,
    "cambio_domicilio": TipoTramite.BAJA,         # usa checklist simplificado hasta v2
    "duplicado_circulacion": TipoTramite.BAJA,     # idem
}
TIPOS_VALIDOS = set(TIPO_TRAMITE_MAP)


# ── Schemas ───────────────────────────────────────────────────────────────────

class TramiteManualCreado(BaseModel):
    tramite_id: str
    tipo: str
    matricula: str | None
    bastidor: str | None
    gestoria: str
    creado_at: str


class DocumentoCargadoResult(BaseModel):
    doc_id: str
    nombre: str
    tipo_detectado: str
    confianza: str
    confianza_score: float
    validez: str   # VALIDO | EVIDENCIA_COMPATIBLE | RECHAZADO | NO_APLICA | PENDIENTE
    campos_extraidos: dict[str, Any]
    justificacion: str


class ResultadoChecklist(BaseModel):
    tramite_id: str
    tipo: str
    completo: bool
    listo_dgt: bool
    requisitos_validos: list[str]
    requisitos_faltantes: list[str]
    requisitos_rechazados: list[str]
    requisitos_evidencia: list[str]
    debe_pedir_gestoria: bool
    documentos: list[DocumentoCargadoResult]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/tramite", response_model=TramiteManualCreado, status_code=201)
def crear_tramite_manual(
    tipo: str = Form(...),
    subtipo: str | None = Form(None),
    matricula: str | None = Form(None),
    bastidor: str | None = Form(None),
    gestoria: str = Form(...),
    gestoria_email: str | None = Form(None),
) -> TramiteManualCreado:
    """Crea un trámite manual. Devuelve tramite_id para subir documentos."""
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            422,
            f"Tipo de trámite no reconocido: '{tipo}'. "
            f"Valores válidos: {', '.join(sorted(TIPOS_VALIDOS))}",
        )
    tramite_id = f"manual-{uuid.uuid4().hex[:8]}"
    ahora = datetime.utcnow().isoformat()
    _tramites_manuales[tramite_id] = {
        "tramite_id": tramite_id,
        "tipo": tipo,
        "subtipo": subtipo,
        "matricula": matricula,
        "bastidor": bastidor,
        "gestoria": gestoria,
        "gestoria_email": gestoria_email or "",
        "creado_at": ahora,
        "documentos": [],            # list[DocumentoCargadoResult]
        "docs_por_requisito": {},    # para evaluar_checklist
    }
    logger.info("Trámite manual creado: %s tipo=%s gestoria=%s", tramite_id, tipo, gestoria)
    return TramiteManualCreado(
        tramite_id=tramite_id,
        tipo=tipo,
        matricula=matricula,
        bastidor=bastidor,
        gestoria=gestoria,
        creado_at=ahora,
    )


@router.post(
    "/tramite/{tramite_id}/documento",
    response_model=DocumentoCargadoResult,
)
async def subir_documento(
    tramite_id: str,
    archivo: UploadFile = File(...),
    tipo_declarado: str | None = Form(None),
) -> DocumentoCargadoResult:
    """Sube un documento a un trámite manual.

    Dispara clasificación + cotejo automáticamente.
    Devuelve tipo detectado, validez y campos extraídos.
    """
    tramite = _tramites_manuales.get(tramite_id)
    if not tramite:
        raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")

    # Guardar en storage
    contenido = await archivo.read()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    nombre = archivo.filename or "documento.pdf"
    mime = archivo.content_type or "application/pdf"
    ruta = guardar_archivo(doc_id, contenido, nombre, mime)

    # Clasificar
    try:
        clf_result = await _clf.clasificar(ruta_archivo=ruta, tipo_declarado=tipo_declarado)
    except Exception as exc:
        logger.error("Error clasificando %s: %s", nombre, exc)
        raise HTTPException(500, f"Error al clasificar el documento: {exc}")

    # Cotejo: usar tipo_detectado como clave de requisito
    req_key = clf_result.tipo_detectado.value
    tramite["docs_por_requisito"][req_key] = clf_result

    tipo_tramite = TIPO_TRAMITE_MAP[tramite["tipo"]]
    estado: EstadoChecklist = _motor.evaluar_checklist(
        tipo_tramite, tramite["docs_por_requisito"]
    )

    # Validez de ESTE documento en concreto
    if req_key in estado.requisitos_validos:
        validez = "VALIDO"
    elif req_key in estado.requisitos_rechazados:
        validez = "RECHAZADO"
    elif req_key in estado.requisitos_evidencia:
        validez = "EVIDENCIA_COMPATIBLE"
    else:
        validez = "PENDIENTE"

    doc_result = DocumentoCargadoResult(
        doc_id=doc_id,
        nombre=nombre,
        tipo_detectado=clf_result.tipo_detectado.value,
        confianza=clf_result.confianza_nivel,
        confianza_score=clf_result.confianza_score,
        validez=validez,
        campos_extraidos=clf_result.datos_extraidos,
        justificacion=clf_result.justificacion,
    )
    tramite["documentos"].append(doc_result.model_dump())

    logger.info(
        "Documento cargado: tramite=%s doc=%s tipo=%s validez=%s confianza=%.2f",
        tramite_id, doc_id, clf_result.tipo_detectado.value, validez, clf_result.confianza_score,
    )
    return doc_result


@router.get("/tramite/{tramite_id}/resultado", response_model=ResultadoChecklist)
def resultado_tramite(tramite_id: str) -> ResultadoChecklist:
    """Estado actual del checklist tras todos los documentos cargados."""
    tramite = _tramites_manuales.get(tramite_id)
    if not tramite:
        raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")

    tipo_tramite = TIPO_TRAMITE_MAP[tramite["tipo"]]
    estado = _motor.evaluar_checklist(tipo_tramite, tramite["docs_por_requisito"])
    listo = estado.completo

    return ResultadoChecklist(
        tramite_id=tramite_id,
        tipo=tramite["tipo"],
        completo=estado.completo,
        listo_dgt=listo,
        requisitos_validos=estado.requisitos_validos,
        requisitos_faltantes=estado.requisitos_faltantes,
        requisitos_rechazados=estado.requisitos_rechazados,
        requisitos_evidencia=estado.requisitos_evidencia,
        debe_pedir_gestoria=estado.debe_pedir_gestoria,
        documentos=[DocumentoCargadoResult(**d) for d in tramite["documentos"]],
    )
