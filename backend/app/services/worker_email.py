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

from app.services.catalogo_documental import TipoTramite, SubtipoTramite
from app.services.deduccion_tipo import deducir_tipo_tramite
from app.services.ingesta_email import AdjuntoEmail, EmailEntrante, FuenteCorreo, IngestaEmail
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services import registro_tramites

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


def _construir_tramite_email(
    tramite_id: str,
    email: EmailEntrante,
    deduccion,
    resultado_pipeline,
) -> dict:
    """Construye el dict de trámite con forma idéntica a carga manual."""
    ahora = datetime.now(timezone.utc).isoformat()
    estado = _estado_tramite(resultado_pipeline)
    alerta = estado in ("pendiente_gestoria", "en_revision", "pendiente_jefatura")

    tipo_str = deduccion.tipo.value if deduccion.tipo else "SIN_DETERMINAR"
    subtipo_str = _SUBTIPO_STR.get(deduccion.subtipo, "ninguno")

    docs = []
    for nombre, clf in resultado_pipeline.clasificaciones.items():
        docs.append({
            "nombre": nombre,
            "tipo_detectado": clf.tipo_detectado.value,
            "confianza": clf.confianza_nivel,
            "estado": "valido" if clf.confianza_score >= 0.7 else "baja_confianza",
        })

    avisos = []
    for msg in resultado_pipeline.mensajes_preparados:
        avisos.append({
            "tipo": msg.tipo.value,
            "enviado_at": ahora,
            "requisito": msg.asunto,
        })

    checklist = resultado_pipeline.estado_checklist
    faltantes = checklist.requisitos_faltantes if checklist else []

    return {
        "id": tramite_id,
        "tipo": tipo_str,
        "subtipo": subtipo_str,
        "matricula": None,
        "bastidor": None,
        "gestoria": email.remitente,       # remitente como texto si no hay match en DB
        "gestoria_email": email.remitente,
        "estado": estado,
        "fecha_entrada": ahora,
        "alerta": alerta,
        "origen": "email",
        "asunto_email": email.asunto,
        "documentos": docs,
        "historial": [{
            "timestamp": ahora,
            "evento": "email_recibido",
            "detalle": f"Email de {email.remitente} con {len(email.adjuntos)} adjunto(s)",
        }],
        "avisos_pendientes": avisos,
        "documentos_faltantes": faltantes,
        "motivo_deduccion": deduccion.motivo,
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

                # Clasificar adjuntos mediante el pipeline y deducir tipo
                # El pipeline clasifica internamente; extraemos los tipos del resultado
                # usando un tramite_id provisional con tipo TRANSFERENCIA como fallback
                # para poder llamar a procesar_email y obtener las clasificaciones.
                resultado = await _pipeline.procesar_email(
                    email_entrante=email,
                    tipo_tramite=TipoTramite.TRANSFERENCIA,  # provisional; se corrige abajo
                    tramite_id=tramite_id,
                    gestoria_email=email.remitente,
                )

                # Deducir tipo real a partir de los tipos clasificados
                tipos_clasificados = [
                    clf.tipo_detectado
                    for clf in resultado.clasificaciones.values()
                ]
                deduccion = deducir_tipo_tramite(tipos_clasificados)

                # DEUDA CAPA 4: trámite guardado en memoria (Opción A).
                # Si el servidor reinicia, los registros de email_procesado y avisos
                # en BD quedarán huérfanos (tramite_id sin tramite en memoria).
                # Solución definitiva: migrar a escribir en tabla tramites de PostgreSQL.
                tramite = _construir_tramite_email(tramite_id, email, deduccion, resultado)
                registro_tramites.agregar_tramite(tramite)

                logger.info(
                    "Trámite %s creado — tipo=%s subtipo=%s estado=%s",
                    tramite_id, tramite["tipo"], tramite["subtipo"], tramite["estado"],
                )

        except asyncio.CancelledError:
            logger.info("Worker email detenido.")
            break
        except Exception:
            logger.exception("Error en ciclo del worker email — reintentando en %ds.", intervalo)

        await asyncio.sleep(intervalo)
