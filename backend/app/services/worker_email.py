"""
Worker de ingesta de email — loop periódico de polling IMAP.

Arrancado desde el lifespan de FastAPI (main.py). Cada `intervalo` segundos:
  1. Carga los Message-IDs ya procesados desde la BD (dedup persistente).
  2. Hace polling IMAP y extrae emails nuevos.
  3. Para cada email con adjuntos útiles:
     a. Clasifica los adjuntos (via Pipeline.procesar_email interno, pero aquí
        primero deduce el tipo antes de llamar al pipeline).
     b. Deduce tipo de trámite con deducir_tipo_tramite().
     c. Crea el trámite en registro_tramites (Opción A híbrida).
     d. Llama a Pipeline.procesar_email() → escribe email_procesado y aviso_1 en BD.

DEUDA CAPA 4: el trámite se crea en registro_tramites (memoria). Si el servidor
reinicia, los email_procesado y avisos de BD quedan apuntando a un tramite_id que
ya no existe en memoria. Migrar carga.py + este worker a escribir en la tabla
tramites de PostgreSQL elimina el problema. Ver docs/matriz-documental-tramites.md §13.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from app.services.catalogo_documental import TipoTramite, SubtipoTramite, FamiliaTramite, TipoDocumento
from app.services.deduccion_tipo import deducir_tipo_tramite
from app.services.ingesta_email import AdjuntoEmail, EmailEntrante, FuenteCorreo, IngestaEmail
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services.gestorias import nombre_gestoria
from app.services.storage import guardar_archivo
from app.api.store import DOCUMENTOS_CARGA
from app.services import registro_tramites
from app.services.correlacion import (
    extraer_identificador,
    serializar_verificaciones as _serializar_verificaciones,
    recotejar_tramite as _recotejar_tramite,
    adjuntar_documentos,
    ingestar_documentos,
)

logger = logging.getLogger(__name__)

# ── Subtipo → string canónico del trámite ─────────────────────────────────────

_SUBTIPO_STR: dict[SubtipoTramite, str] = {
    SubtipoTramite.NINGUNO: "ninguno",
    SubtipoTramite.HERENCIA: "herencia",
    SubtipoTramite.COMPRAVENTA_PARTICULAR: "compraventa_particular",
    SubtipoTramite.COMPRA_EMPRESA: "compra_empresa",
    SubtipoTramite.NUEVO: "nuevo",
    SubtipoTramite.USADO: "usado",
}


def _estado_tramite(resultado_pipeline) -> str:
    """Traduce el resultado del pipeline al estado canónico del trámite."""
    if resultado_pipeline.listo_dgt:
        return "listo_dgt"
    if resultado_pipeline.no_telematico:
        return "pendiente_jefatura"
    checklist = resultado_pipeline.estado_checklist
    if checklist is not None and checklist.debe_escalar_admin:
        return "pendiente_gestoria"
    if checklist is not None and not checklist.completo:
        return "pendiente_gestoria"
    if resultado_pipeline.error:
        return "en_revision"
    return "en_revision"



async def adjuntar_a_tramite(
    tramite: dict,
    email: EmailEntrante,
    clasificaciones: dict,
) -> None:
    """Adjunta documentos de una respuesta de email a un trámite existente y re-coteja."""
    archivos = {a.nombre: (a.contenido, a.content_type) for a in email.adjuntos}
    adjuntar_documentos(tramite, clasificaciones, email.remitente, archivos=archivos)


def _construir_tramite_email(
    tramite_id: str,
    email: EmailEntrante,
    deduccion,
    resultado_pipeline,
) -> dict:
    """Construye el dict de trámite con forma idéntica a carga manual.

    También registra cada documento en DOCUMENTOS_CARGA para que
    /api/documentos/{id}/extraccion los sirva.
    """
    ahora = datetime.now(timezone.utc).isoformat()
    estado = _estado_tramite(resultado_pipeline)
    alerta = estado in ("pendiente_gestoria", "en_revision", "pendiente_jefatura")

    tipo_str = deduccion.tipo.value if deduccion.tipo else "SIN_DETERMINAR"
    subtipo_str = _SUBTIPO_STR.get(deduccion.subtipo, "ninguno")

    checklist = resultado_pipeline.estado_checklist
    faltantes = checklist.requisitos_faltantes if checklist else []
    evidencia = checklist.requisitos_evidencia if checklist else []

    # Construir detalle de campos faltantes por documento de evidencia
    # (qué campos concretos faltan en cada clasificación con baja confianza)
    evidencia_detalle: dict[str, list[str]] = {}
    for nombre_doc, clf in resultado_pipeline.clasificaciones.items():
        tipo_doc = clf.tipo_detectado.value if clf.tipo_detectado else ""
        if tipo_doc in evidencia:
            from app.services.catalogo_documental import CAMPOS_REQUERIDOS
            requeridos = CAMPOS_REQUERIDOS.get(clf.tipo_detectado, [])
            extraidos = set(clf.datos_extraidos or {})
            campos_faltantes = [c for c in requeridos if c not in extraidos]
            if campos_faltantes:
                evidencia_detalle[tipo_doc] = campos_faltantes

    # Construir la validez por tipo desde el checklist
    validez_por_tipo: dict[str, str] = {}
    if checklist:
        for t in checklist.requisitos_validos:
            validez_por_tipo[t] = "VALIDO"
        for t in checklist.requisitos_evidencia:
            validez_por_tipo.setdefault(t, "EVIDENCIA_COMPATIBLE")
        for t in checklist.requisitos_rechazados:
            validez_por_tipo.setdefault(t, "RECHAZADO")
        for t in checklist.requisitos_faltantes:
            validez_por_tipo.setdefault(t, "FALTANTE")

    # Índice nombre → adjunto para guardar el archivo original
    adjunto_por_nombre = {a.nombre: a for a in email.adjuntos}

    docs = []
    for i, (nombre, clf) in enumerate(resultado_pipeline.clasificaciones.items()):
        doc_id = f"{tramite_id}-doc-{i}"
        tipo_doc = clf.tipo_detectado.value
        validez = validez_por_tipo.get(tipo_doc, "VALIDO" if clf.confianza_score >= 0.7 else "BAJA_CONFIANZA")
        campos = [
            {"campo": k, "valor": str(v), "estado": "valido"}
            for k, v in (clf.datos_extraidos or {}).items()
        ]

        # Guardar el archivo original en storage (mismo mecanismo que carga manual)
        tiene_archivo = False
        adjunto = adjunto_por_nombre.get(nombre)
        if adjunto is not None and adjunto.contenido:
            try:
                guardar_archivo(doc_id, adjunto.contenido, nombre, adjunto.content_type)
                tiene_archivo = True
            except Exception as exc:
                logger.warning("No se pudo guardar adjunto '%s' doc_id=%s: %s", nombre, doc_id, exc)

        doc_entry = {
            "id": doc_id,
            "tramite_id": tramite_id,
            "nombre": nombre,
            "tipo_detectado": tipo_doc,
            "validez": validez,
            "confianza": clf.confianza_nivel,
            "confianza_score": clf.confianza_score,
            "tiene_archivo": tiene_archivo,
            "campos_extraidos": campos,
            "justificacion": clf.justificacion or "",
        }
        DOCUMENTOS_CARGA[doc_id] = doc_entry
        docs.append({
            "id": doc_id,
            "nombre": nombre,
            "tipo_detectado": tipo_doc,
            "validez": validez,
            "confianza": clf.confianza_nivel,
        })

    avisos = []
    for msg in resultado_pipeline.mensajes_preparados:
        avisos.append({
            "tipo": msg.tipo.value,
            "enviado_at": ahora,
            "requisito": msg.asunto,
        })

    matricula, bastidor = extraer_identificador(tipo_str, resultado_pipeline.clasificaciones)
    verificaciones = _serializar_verificaciones(checklist, resultado_pipeline.clasificaciones)

    from app.services.motor_cruce import cotejar_datos as _cotejar_datos
    docs_por_tipo_email = {
        clf.tipo_detectado.value: (clf.datos_extraidos or {})
        for clf in resultado_pipeline.clasificaciones.values()
        if hasattr(clf, "tipo_detectado") and clf.tipo_detectado
    }
    cruces = _cotejar_datos(tipo_str, subtipo_str, docs_por_tipo_email)
    verificaciones = verificaciones + cruces

    return {
        "id": tramite_id,
        "tipo": tipo_str,
        "subtipo": subtipo_str,
        "matricula": matricula,
        "bastidor": bastidor,
        "gestoria": nombre_gestoria(email.remitente),
        "gestoria_email": email.remitente,
        "estado": estado,
        "fecha_entrada": ahora,
        "alerta": alerta,
        "origen": "email",
        "asunto_email": email.asunto,
        "documentos": docs,
        "historial": [{
            "momento": ahora,
            "evento": f"Email de {email.remitente} con {len(email.adjuntos)} adjunto(s)",
            "actor": "tyrion",
        }],
        "avisos_pendientes": avisos,
        "documentos_faltantes": faltantes,
        "documentos_evidencia": evidencia,
        "documentos_evidencia_detalle": evidencia_detalle,
        "motivo_deduccion": deduccion.motivo,
        "verificaciones": verificaciones,
    }


async def run_email_worker(
    intervalo: int = 60,
    fuente: FuenteCorreo | None = None,
    repo=None,
    pipeline: Pipeline | None = None,
) -> None:
    """Loop periódico de ingesta de email. Arrancado desde lifespan de FastAPI.

    Parámetros inyectables para tests:
      fuente   — FuenteCorreo alternativa (mock sin red)
      repo     — RepositorioPipeline (mock sin BD)
      pipeline — Pipeline preconfigurado (mock clasificador)
    """
    _repo = repo or RepositorioEnMemoria()
    _pipeline = pipeline or Pipeline(repo=_repo)
    ingesta = IngestaEmail(fuente=fuente)

    logger.info("Worker email arrancado (intervalo=%ds).", intervalo)

    while True:
        try:
            vistos = _repo.mensaje_ids_procesados()
            # poll() hace I/O IMAP síncrono (imaplib) — se corre en thread aparte
            # para no bloquear el event loop de asyncio durante connect/login/fetch.
            nuevos = await asyncio.to_thread(ingesta.poll, vistos)

            for email in nuevos:
                if not email.tiene_adjuntos_utiles:
                    logger.info(
                        "Email %s de %s sin adjuntos útiles — descartado.",
                        email.message_id, email.remitente,
                    )
                    continue

                tramite_id = str(uuid4())
                logger.info(
                    "Procesando email %s de %s (%d adjuntos) → tramite %s",
                    email.message_id, email.remitente,
                    len(email.adjuntos), tramite_id,
                )

                # PASO 1: Clasificar adjuntos sin correr el checklist
                clasificaciones = await _pipeline.clasificar_adjuntos(email)

                async def _crear_tramite_email(tid: str, mat: str | None, bas: str | None) -> dict:
                    tipos_clasificados = [clf.tipo_detectado for clf in clasificaciones.values()]
                    deduccion = deducir_tipo_tramite(tipos_clasificados)
                    resultado = await _pipeline.procesar_email(
                        email_entrante=email,
                        tipo_tramite=deduccion.tipo or TipoTramite.TRANSFERENCIA,
                        tramite_id=tid,
                        gestoria_email=email.remitente,
                        subtipo_tramite=deduccion.subtipo or SubtipoTramite.NINGUNO,
                    )
                    return _construir_tramite_email(tid, email, deduccion, resultado)

                tramite, es_nuevo = await ingestar_documentos(
                    clasificaciones=clasificaciones,
                    crear_tramite_fn=_crear_tramite_email,
                    in_reply_to=email.in_reply_to or None,
                    references=email.references or None,
                    asunto=email.asunto or None,
                    archivos={a.nombre: (a.contenido, a.content_type) for a in email.adjuntos},
                    remitente=email.remitente,
                    tramite_id_nuevo=tramite_id,
                )

                if es_nuevo:
                    logger.info(
                        "Trámite %s creado — tipo=%s subtipo=%s estado=%s",
                        tramite_id, tramite.get("tipo"), tramite.get("subtipo"), tramite.get("estado"),
                    )
                else:
                    logger.info(
                        "Email %s correlacionado con trámite %s — documentos adjuntados, cotejo actualizado.",
                        email.message_id, tramite["id"],
                    )

        except asyncio.CancelledError:
            logger.info("Worker email detenido.")
            break
        except Exception:
            logger.exception("Error en ciclo del worker email — reintentando en %ds.", intervalo)

        await asyncio.sleep(intervalo)
