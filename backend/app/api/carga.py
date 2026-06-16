"""
API de carga manual de documentos (sesión 12 — reescritura).

Principio rector: el administrativo arrastra documentos; Tyrion deduce el resto.
El tipo de trámite NO lo declara el usuario — lo infiere el clasificador viendo
los documentos.

Flujo en dos pasos:

  1. POST /api/carga/documentos   (multipart, 1..N archivos)
     · Clasifica cada archivo con el clasificador activo (OpenAI / mock)
     · Guarda el archivo en storage
     · Devuelve la lista clasificada — NO crea trámite todavía

  2. POST /api/carga/procesar     (JSON: sesion_id + datos opcionales)
     · Deduce el tipo de trámite a partir de los documentos (documento principal)
     · Crea el trámite, evalúa el checklist y los cruces multi-documento
     · Determina estado (listo_dgt / pendiente_gestoria) y prepara avisos
     · Registra el trámite → aparece en la Pantalla de Control

  3. GET  /api/carga/sesion/{sesion_id}   — estado de la sesión de carga
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.catalogo_documental import (
    TipoDocumento,
    TipoTramite,
    FamiliaTramite,
    SubtipoTramite,
)
from app.services.clasificador import ClasificadorDocumental
from app.services.deduccion_tipo import deducir_tipo_tramite
from app.services.motor_cotejo import (
    MotorCotejo,
    EstadoChecklist,
    RequisitoCotejo,
    resolver_checklist,
)
from app.services import registro_tramites
from app.services.storage import guardar_archivo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/carga", tags=["carga"])

_clf = ClasificadorDocumental()
_motor = MotorCotejo()

# TipoTramite (3 valores del motor v1) → FamiliaTramite (árbol completo)
_FAMILIA_DE_TIPO: dict[TipoTramite, FamiliaTramite] = {
    TipoTramite.TRANSFERENCIA: FamiliaTramite.TRANSFERENCIA,
    TipoTramite.MATRICULACION: FamiliaTramite.MATRICULACION,
    TipoTramite.BAJA: FamiliaTramite.BAJA,
}

# Etiquetas legibles del tipo deducido para mostrar al administrativo
_ETIQUETA_TIPO: dict[tuple[str, str], str] = {
    ("TRANSFERENCIA", "ninguno"):   "Transferencia",
    ("TRANSFERENCIA", "herencia"):  "Transferencia por herencia",
    ("MATRICULACION", "ninguno"):   "Matriculación",
    ("BAJA", "ninguno"):            "Baja",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class DocumentoClasificado(BaseModel):
    doc_id: str
    archivo: str
    tipo_detectado: str
    confianza: str
    confianza_score: float
    justificacion: str = ""


class SubirDocumentosResponse(BaseModel):
    sesion_id: str
    documentos: list[DocumentoClasificado]


class ProcesarRequest(BaseModel):
    sesion_id: str
    gestoria: str | None = None
    gestoria_email: str | None = None
    matricula: str | None = None
    bastidor: str | None = None


class ProcesarResponse(BaseModel):
    tramite_id: str
    tipo_tramite: str | None
    tipo_label: str
    subtipo: str
    deduccion_motivo: str
    estado: str
    estado_label: str
    listo_dgt: bool
    requisitos_validos: list[str]
    requisitos_faltantes: list[str]
    requisitos_evidencia: list[str]
    requisitos_rechazados: list[str]
    debe_pedir_gestoria: bool
    aviso_preparado: bool
    documentos: list[DocumentoClasificado]


class SesionResponse(BaseModel):
    sesion_id: str
    creada_at: str
    num_documentos: int
    documentos: list[DocumentoClasificado]
    tramite_id: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

_ESTADO_LABEL = {
    "listo_dgt": "Listo DGT",
    "pendiente_gestoria": "Pendiente gestoría",
    "en_revision": "En revisión",
}


def _requisitos_del_tipo(tipo: TipoTramite, subtipo: SubtipoTramite) -> list[RequisitoCotejo]:
    """Resuelve el checklist correcto (incluye reglas de subtipo como herencia)."""
    familia = _FAMILIA_DE_TIPO[tipo]
    checklist = resolver_checklist(familia=familia, subtipo=subtipo)
    return [RequisitoCotejo(requisito=r) for r in checklist.requisitos]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/documentos", response_model=SubirDocumentosResponse)
async def subir_documentos(
    archivos: list[UploadFile] = File(...),
    sesion_id: str | None = Form(None),
) -> SubirDocumentosResponse:
    """Sube 1..N documentos. Clasifica cada uno; NO crea trámite todavía."""
    if not archivos:
        raise HTTPException(422, "No se recibió ningún archivo.")

    if not sesion_id:
        sesion_id = f"sesion-{uuid.uuid4().hex[:8]}"
        registro_tramites.crear_sesion(sesion_id)
    elif registro_tramites.obtener_sesion(sesion_id) is None:
        registro_tramites.crear_sesion(sesion_id)

    clasificados: list[DocumentoClasificado] = []
    for archivo in archivos:
        contenido = await archivo.read()
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        nombre = archivo.filename or "documento.pdf"
        mime = archivo.content_type or "application/pdf"
        ruta = guardar_archivo(doc_id, contenido, nombre, mime)

        try:
            clf = await _clf.clasificar(ruta_archivo=ruta)
        except Exception as exc:
            logger.error("Error clasificando %s: %s", nombre, exc)
            raise HTTPException(500, f"Error al clasificar '{nombre}': {exc}")

        doc = DocumentoClasificado(
            doc_id=doc_id,
            archivo=nombre,
            tipo_detectado=clf.tipo_detectado.value,
            confianza=clf.confianza_nivel,
            confianza_score=clf.confianza_score,
            justificacion=clf.justificacion,
        )
        clasificados.append(doc)

        # Guardar en la sesión (con la clasificación completa para el cotejo)
        registro_tramites.agregar_documento_a_sesion(sesion_id, {
            **doc.model_dump(),
            "ruta": ruta,
            "_clasificacion": clf,
        })
        logger.info(
            "Documento clasificado: sesion=%s doc=%s tipo=%s confianza=%.2f",
            sesion_id, doc_id, clf.tipo_detectado.value, clf.confianza_score,
        )

    return SubirDocumentosResponse(sesion_id=sesion_id, documentos=clasificados)


@router.post("/procesar", response_model=ProcesarResponse)
def procesar_sesion(payload: ProcesarRequest) -> ProcesarResponse:
    """Deduce el tipo de trámite, evalúa el checklist y crea el trámite.

    El trámite creado aparece en la Pantalla de Control.
    """
    sesion = registro_tramites.obtener_sesion(payload.sesion_id)
    if sesion is None:
        raise HTTPException(404, f"Sesión '{payload.sesion_id}' no encontrada.")
    if not sesion["documentos"]:
        raise HTTPException(422, "La sesión no tiene documentos para procesar.")

    docs_sesion = sesion["documentos"]
    tipos_detectados = [TipoDocumento(d["tipo_detectado"]) for d in docs_sesion]

    # 1. Deducir el tipo de trámite a partir de los documentos
    deduccion = deducir_tipo_tramite(tipos_detectados)
    logger.info("Deducción de tipo: %s", deduccion.motivo)

    tramite_id = f"manual-{uuid.uuid4().hex[:8]}"
    ahora = datetime.now(timezone.utc).isoformat()

    docs_resumen = [
        DocumentoClasificado(
            doc_id=d["doc_id"], archivo=d["archivo"],
            tipo_detectado=d["tipo_detectado"], confianza=d["confianza"],
            confianza_score=d["confianza_score"], justificacion=d.get("justificacion", ""),
        )
        for d in docs_sesion
    ]

    # Caso: no se pudo deducir el tipo → trámite en revisión manual
    if not deduccion.deducido:
        estado_str = "en_revision"
        tramite = _construir_tramite(
            tramite_id, None, payload, docs_sesion, estado_str, ahora,
            alerta=True, motivo=deduccion.motivo,
        )
        registro_tramites.agregar_tramite(tramite)
        registro_tramites.marcar_sesion_procesada(payload.sesion_id, tramite_id)
        return ProcesarResponse(
            tramite_id=tramite_id, tipo_tramite=None,
            tipo_label="Sin determinar", subtipo="ninguno",
            deduccion_motivo=deduccion.motivo,
            estado=estado_str, estado_label=_ESTADO_LABEL[estado_str],
            listo_dgt=False,
            requisitos_validos=[], requisitos_faltantes=[],
            requisitos_evidencia=[], requisitos_rechazados=[],
            debe_pedir_gestoria=False, aviso_preparado=False,
            documentos=docs_resumen,
        )

    tipo = deduccion.tipo
    subtipo = deduccion.subtipo

    # 2. Evaluar el checklist con el tipo (y subtipo) correcto
    docs_por_requisito = {
        d["tipo_detectado"]: d["_clasificacion"] for d in docs_sesion
    }
    requisitos = _requisitos_del_tipo(tipo, subtipo)
    estado: EstadoChecklist = _motor.evaluar_checklist(
        tipo, docs_por_requisito, requisitos=requisitos
    )

    # 3. Determinar estado y preparar aviso si falta documentación
    aviso_preparado = False
    if estado.completo:
        estado_str = "listo_dgt"
    elif estado.debe_pedir_gestoria:
        estado_str = "pendiente_gestoria"
        cuerpo = _motor.preparar_mensaje_gestoria(estado, matricula=payload.matricula)
        aviso_preparado = bool(cuerpo)
    else:
        estado_str = "en_revision"

    listo_dgt = estado.completo

    tramite = _construir_tramite(
        tramite_id, tipo, payload, docs_sesion, estado_str, ahora,
        alerta=(estado_str == "pendiente_gestoria"),
        motivo=deduccion.motivo, subtipo=subtipo.value,
        aviso_preparado=aviso_preparado,
        faltantes=estado.requisitos_faltantes,
    )
    registro_tramites.agregar_tramite(tramite)
    registro_tramites.marcar_sesion_procesada(payload.sesion_id, tramite_id)

    logger.info(
        "Trámite manual %s creado: tipo=%s estado=%s listo_dgt=%s aviso=%s",
        tramite_id, tipo.value, estado_str, listo_dgt, aviso_preparado,
    )

    tipo_label = _ETIQUETA_TIPO.get((tipo.value, subtipo.value), tipo.value.title())

    return ProcesarResponse(
        tramite_id=tramite_id,
        tipo_tramite=tipo.value,
        tipo_label=tipo_label,
        subtipo=subtipo.value,
        deduccion_motivo=deduccion.motivo,
        estado=estado_str,
        estado_label=_ESTADO_LABEL[estado_str],
        listo_dgt=listo_dgt,
        requisitos_validos=estado.requisitos_validos,
        requisitos_faltantes=estado.requisitos_faltantes,
        requisitos_evidencia=estado.requisitos_evidencia,
        requisitos_rechazados=estado.requisitos_rechazados,
        debe_pedir_gestoria=estado.debe_pedir_gestoria,
        aviso_preparado=aviso_preparado,
        documentos=docs_resumen,
    )


@router.get("/sesion/{sesion_id}", response_model=SesionResponse)
def estado_sesion(sesion_id: str) -> SesionResponse:
    """Estado de una sesión de carga: documentos subidos y trámite creado."""
    sesion = registro_tramites.obtener_sesion(sesion_id)
    if sesion is None:
        raise HTTPException(404, f"Sesión '{sesion_id}' no encontrada.")
    docs = [
        DocumentoClasificado(
            doc_id=d["doc_id"], archivo=d["archivo"],
            tipo_detectado=d["tipo_detectado"], confianza=d["confianza"],
            confianza_score=d["confianza_score"], justificacion=d.get("justificacion", ""),
        )
        for d in sesion["documentos"]
    ]
    return SesionResponse(
        sesion_id=sesion_id,
        creada_at=sesion["creada_at"],
        num_documentos=len(docs),
        documentos=docs,
        tramite_id=sesion.get("tramite_id"),
    )


# ── Construcción del trámite (forma idéntica a TRAMITES_PRUEBA) ────────────────

def _construir_tramite(
    tramite_id: str,
    tipo: TipoTramite | None,
    payload: ProcesarRequest,
    docs_sesion: list[dict[str, Any]],
    estado_str: str,
    ahora: str,
    *,
    alerta: bool,
    motivo: str,
    subtipo: str = "ninguno",
    aviso_preparado: bool = False,
    faltantes: list[str] | None = None,
) -> dict[str, Any]:
    """Crea el dict del trámite con la forma que espera la Pantalla de Control."""
    documentos = [
        {
            "id": d["doc_id"],
            "nombre": d["archivo"],
            "tipo_detectado": d["tipo_detectado"],
            "validez": "VALIDO",   # validez por requisito se refina en detalle
            "confianza": d["confianza"],
        }
        for d in docs_sesion
    ]
    historial = [
        {"momento": ahora, "evento": f"Carga manual de {len(docs_sesion)} documento(s)",
         "actor": "admin_web"},
        {"momento": ahora, "evento": motivo, "actor": "tyrion"},
    ]
    avisos_pendientes = []
    if aviso_preparado:
        avisos_pendientes.append({
            "tipo": "AVISO_1",
            "asunto": "Documentación pendiente",
            "preparado_at": ahora,
            "faltantes": faltantes or [],
        })

    return {
        "id": tramite_id,
        "tipo": tipo.value if tipo else "SIN_DETERMINAR",
        "subtipo": subtipo,
        "matricula": payload.matricula,
        "bastidor": payload.bastidor,
        "gestoria": payload.gestoria or "(sin asignar)",
        "gestoria_email": payload.gestoria_email or "",
        "estado": estado_str,
        "fecha_entrada": ahora,
        "alerta": alerta,
        "origen": "carga_manual",
        "documentos": documentos,
        "historial": historial,
        "avisos_pendientes": avisos_pendientes,
    }
