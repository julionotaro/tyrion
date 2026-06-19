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
from app.services.gestorias import nombre_gestoria
from app.services.storage import guardar_archivo
from app.api.store import DOCUMENTOS_CARGA
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


def _extraer_matricula_bastidor(clasificaciones: dict) -> tuple[str | None, str | None]:
    """Extrae matrícula y bastidor de los campos clasificados de los documentos."""
    matricula = None
    bastidor = None
    for clf in clasificaciones.values():
        datos = clf.datos_extraidos or {}
        if matricula is None:
            matricula = datos.get("matricula") or None
        if bastidor is None:
            bastidor = datos.get("bastidor") or datos.get("num_bastidor") or None
        if matricula and bastidor:
            break
    return matricula, bastidor


def _serializar_verificaciones(checklist, clasificaciones: dict) -> list[dict]:
    """Convierte el EstadoChecklist y clasificaciones en la lista verificaciones[] del frontend.

    Genera una tarjeta por requisito del checklist:
    - ok=True si el requisito está validado
    - ok=False si está rechazado o faltante (con vals[] para mostrar la discrepancia)
    """
    if checklist is None:
        return []
    verifs: list[dict] = []

    # Índice tipo_detectado → campos extraídos del documento
    campos_por_tipo: dict[str, dict] = {}
    for clf in clasificaciones.values():
        tipo = clf.tipo_detectado.value if clf.tipo_detectado else "desconocido"
        campos_por_tipo[tipo] = clf.datos_extraidos or {}

    for req in checklist.requisitos_validos:
        datos = campos_por_tipo.get(req, {})
        # Intentar obtener un valor representativo para mostrar
        valor = (
            datos.get("matricula")
            or datos.get("bastidor")
            or datos.get("num_bastidor")
            or datos.get("dni")
            or "presente"
        )
        verifs.append({
            "campo": req,
            "ok": True,
            "descripcion": f"{req.replace('_', ' ').capitalize()} validado",
            "valor": str(valor),
            "docs": [req],
        })

    for req in checklist.requisitos_evidencia:
        nombre_req = req.replace("_", " ")
        verifs.append({
            "campo": req,
            "ok": False,
            "descripcion": f"{nombre_req.capitalize()} — recibido pero insuficiente",
            "vals": [
                {"doc": "Documento recibido", "val": f"{req} (baja confianza)"},
                {"doc": "Estado", "val": "Evidencia compatible — no válido"},
            ],
            "aviso": (
                f"El {nombre_req} fue recibido pero no pudo validarse "
                f"(confianza insuficiente o campos incompletos). "
                f"Por favor reenvíen el documento en mejor calidad o formato digital."
            ),
        })

    for req in checklist.requisitos_rechazados:
        tipo_recibido = next(
            (t for t in campos_por_tipo if t != req), "desconocido"
        )
        nombre_req = req.replace("_", " ")
        verifs.append({
            "campo": req,
            "ok": False,
            "descripcion": f"Documento recibido no corresponde al tipo requerido ({req})",
            "vals": [
                {"doc": "Documento recibido", "val": tipo_recibido},
                {"doc": "Tipo requerido", "val": req},
            ],
            "aviso": (
                f"El documento enviado no es del tipo requerido. "
                f"Se necesita: {nombre_req}. "
                f"Por favor, reenvíen el documento correcto."
            ),
        })

    for req in checklist.requisitos_faltantes:
        nombre_req = req.replace("_", " ")
        verifs.append({
            "campo": req,
            "ok": False,
            "descripcion": f"Falta {nombre_req} — no recibido",
            "vals": [
                {"doc": "Documento recibido", "val": "—"},
                {"doc": "Tipo requerido", "val": req},
            ],
            "aviso": (
                f"No se recibió el {nombre_req}. "
                f"Por favor envíenlo para completar el expediente."
            ),
        })

    return verifs


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

    matricula, bastidor = _extraer_matricula_bastidor(resultado_pipeline.clasificaciones)
    verificaciones = _serializar_verificaciones(checklist, resultado_pipeline.clasificaciones)

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

                # PASO 2: Deducir tipo y subtipo reales a partir de las clasificaciones
                tipos_clasificados = [clf.tipo_detectado for clf in clasificaciones.values()]
                deduccion = deducir_tipo_tramite(tipos_clasificados)

                # PASO 3: Correr el pipeline completo con tipo y subtipo correctos
                resultado = await _pipeline.procesar_email(
                    email_entrante=email,
                    tipo_tramite=deduccion.tipo or TipoTramite.TRANSFERENCIA,
                    tramite_id=tramite_id,
                    gestoria_email=email.remitente,
                    subtipo_tramite=deduccion.subtipo or SubtipoTramite.NINGUNO,
                )

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
