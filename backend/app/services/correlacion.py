"""Correlación de documentos con trámites existentes y re-cotejo compartido.

Módulo sin dependencias circulares: importado por worker_email.py y carga.py.
"""
from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.services.catalogo_documental import TipoTramite, SubtipoTramite, FamiliaTramite, TipoDocumento
from app.api.store import DOCUMENTOS_CARGA
from app.services.storage import guardar_archivo

logger = logging.getLogger(__name__)


def extraer_identificador(
    tipo_tramite: str,
    clasificaciones_o_docs,
) -> tuple[str | None, str | None]:
    """Extrae (matricula, bastidor) buscando en TODOS los documentos.

    - TRANSFERENCIA / BAJA: matrícula es el identificador principal.
    - MATRICULACION: bastidor es el identificador principal (no hay matrícula aún).

    `clasificaciones_o_docs` puede ser:
    - dict {nombre: ResultadoClasificacion}  — tiene .datos_extraidos dict
    - dict {nombre: dict}                    — tiene campos_extraidos list[{campo, valor}]
    """
    matricula: str | None = None
    bastidor: str | None = None

    items = clasificaciones_o_docs.values() if hasattr(clasificaciones_o_docs, "values") else clasificaciones_o_docs

    for item in items:
        if hasattr(item, "datos_extraidos"):
            datos = item.datos_extraidos or {}
        elif isinstance(item, dict):
            campos = item.get("campos_extraidos") or []
            datos = {c["campo"]: c["valor"] for c in campos if isinstance(c, dict)}
            datos.update(item.get("datos_extraidos") or {})
        else:
            datos = {}

        # Matrícula: varios nombres posibles según clasificador
        mat = (
            datos.get("matricula")
            or datos.get("matricula_vehiculo")
            or datos.get("num_matricula")
            or datos.get("matricula_actual")
            or None
        )
        # Bastidor/VIN: varios nombres posibles
        bas = (
            datos.get("bastidor")
            or datos.get("num_bastidor")
            or datos.get("vin")
            or datos.get("num_vin")
            or None
        )

        if mat and matricula is None:
            from app.services.registro_tramites import normalizar_matricula
            matricula = normalizar_matricula(mat)
        if bas and bastidor is None:
            from app.services.registro_tramites import normalizar_bastidor
            bastidor = normalizar_bastidor(bas)

    return matricula, bastidor


def _reconstruir_clf_desde_doc(doc_entry: dict):
    """Reconstruye un ResultadoClasificacion mínimo desde un doc guardado en DOCUMENTOS_CARGA."""
    from app.schemas.clasificacion import ResultadoClasificacion
    try:
        tipo = TipoDocumento(doc_entry["tipo_detectado"])
        datos = {c["campo"]: c["valor"] for c in doc_entry.get("campos_extraidos", [])}
        return ResultadoClasificacion(
            tipo_detectado=tipo,
            confianza_score=doc_entry.get("confianza_score", 0.8),
            confianza_nivel=doc_entry.get("confianza", "ALTA"),
            datos_extraidos=datos,
        )
    except Exception:
        return None


def serializar_verificaciones(checklist, clasificaciones: dict) -> list[dict]:
    """Convierte EstadoChecklist + clasificaciones en verificaciones[] para el frontend."""
    if checklist is None:
        return []
    verifs: list[dict] = []

    campos_por_tipo: dict[str, dict] = {}
    for clf in clasificaciones.values():
        if hasattr(clf, "tipo_detectado"):
            tipo = clf.tipo_detectado.value if clf.tipo_detectado else "desconocido"
            campos_por_tipo[tipo] = clf.datos_extraidos or {}

    for req in checklist.requisitos_validos:
        datos = campos_por_tipo.get(req, {})
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
        tipo_recibido = next((t for t in campos_por_tipo if t != req), "desconocido")
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


def recotejar_tramite(tramite: dict) -> None:
    """Re-ejecuta el cotejo sobre el conjunto completo de documentos del trámite."""
    from app.services.motor_cotejo import MotorCotejo, RequisitoCotejo, resolver_checklist

    docs_por_requisito: dict = {}
    for doc_ref in tramite.get("documentos", []):
        doc_id = doc_ref.get("id")
        full = DOCUMENTOS_CARGA.get(doc_id) if doc_id else None
        if full is None:
            full = {
                "tipo_detectado": doc_ref.get("tipo_detectado", "sin_determinar"),
                "confianza_score": 0.8,
                "confianza": doc_ref.get("confianza", "ALTA"),
                "campos_extraidos": [],
            }
        clf = _reconstruir_clf_desde_doc(full)
        if clf is not None:
            docs_por_requisito[clf.tipo_detectado.value] = clf

    try:
        tipo_tramite = TipoTramite(tramite.get("tipo", "TRANSFERENCIA"))
    except ValueError:
        tipo_tramite = TipoTramite.TRANSFERENCIA

    subtipo_str = tramite.get("subtipo", "ninguno")
    try:
        subtipo_tramite = SubtipoTramite(subtipo_str)
    except ValueError:
        subtipo_tramite = SubtipoTramite.NINGUNO

    requisitos = None
    if subtipo_tramite != SubtipoTramite.NINGUNO:
        _familia_map = {
            TipoTramite.TRANSFERENCIA: FamiliaTramite.TRANSFERENCIA,
            TipoTramite.MATRICULACION: FamiliaTramite.MATRICULACION,
            TipoTramite.BAJA: FamiliaTramite.BAJA,
        }
        familia = _familia_map.get(tipo_tramite)
        if familia is not None:
            cr = resolver_checklist(familia, subtipo=subtipo_tramite)
            requisitos = [RequisitoCotejo(r) for r in cr.requisitos]

    motor = MotorCotejo()
    checklist = motor.evaluar_checklist(
        tipo_tramite, docs_por_requisito, requisitos=requisitos,
        familia=tipo_tramite.value, subtipo=subtipo_str,
    )

    from app.services.motor_cruce import cotejar_datos as _cotejar_datos
    tipo_tramite_str = tramite.get("tipo", "")
    subtipo_cruce = tramite.get("subtipo", "ninguno")
    docs_por_tipo: dict[str, dict] = {}
    for doc in tramite.get("documentos", []):
        tipo_doc = doc.get("tipo_detectado", "")
        doc_id = doc.get("id", "")
        doc_store = DOCUMENTOS_CARGA.get(doc_id, {})
        campos = doc_store.get("campos_extraidos") or []
        datos = {c["campo"]: c["valor"] for c in campos}
        if tipo_doc and datos:
            docs_por_tipo.setdefault(tipo_doc, {}).update(datos)
    verifs = _cotejar_datos(tipo_tramite_str, subtipo_cruce, docs_por_tipo)
    tramite["verificaciones_cruce"] = verifs

    tramite["verificaciones"] = serializar_verificaciones(checklist, docs_por_requisito) + verifs
    tramite["documentos_faltantes"] = checklist.requisitos_faltantes
    tramite["documentos_evidencia"] = checklist.requisitos_evidencia

    if checklist.completo:
        tramite["estado"] = "listo_dgt"
        tramite["alerta"] = False
        tramite["avisos_pendientes"] = []
        tramite["documentos_faltantes"] = []
        tramite["documentos_evidencia"] = []
        tramite["documentos_evidencia_detalle"] = {}
    else:
        tramite["estado"] = "pendiente_gestoria"
        tramite["alerta"] = True

    # Reabrir si tenía listo_dgt pero hay discrepancias CRÍTICAS
    if tramite.get("estado") == "listo_dgt":
        criticas = [
            v for v in verifs
            if v.get("estado") == "discrepancia" and v.get("criticidad") == "CRITICA"
        ]
        if criticas:
            tramite["estado"] = "pendiente_gestoria"
            tramite["alerta"] = True
            tramite.setdefault("historial", []).append({
                "momento": datetime.now(timezone.utc).isoformat(),
                "evento": f"Re-abierto por discrepancia crítica: {criticas[0].get('aviso','')}",
                "actor": "tyrion",
            })


def adjuntar_documentos(
    tramite: dict,
    clasificaciones: dict,
    remitente: str,
    archivos: dict | None = None,
    doc_ids: dict | None = None,
) -> None:
    """Adjunta documentos clasificados a un trámite existente y re-coteja.

    Args:
        tramite: dict del trámite (modificado in-place).
        clasificaciones: {nombre_archivo: ResultadoClasificacion}
        remitente: para el historial.
        archivos: {nombre_archivo: (bytes, content_type)} — guarda si se proveen.
        doc_ids: {nombre_archivo: doc_id} — reutiliza IDs ya asignados (carga manual).
    """
    ahora = datetime.now(timezone.utc).isoformat()
    tramite_id = tramite["id"]
    existing_count = len(tramite.get("documentos", []))
    nuevos_nombres: list[str] = []

    for i, (nombre, clf) in enumerate(clasificaciones.items()):
        doc_id = (doc_ids or {}).get(nombre) or f"{tramite_id}-doc-{existing_count + i}"
        tipo_doc = clf.tipo_detectado.value
        campos = [
            {"campo": k, "valor": str(v), "estado": "valido"}
            for k, v in (clf.datos_extraidos or {}).items()
        ]

        tiene_archivo = False
        if archivos and nombre in archivos:
            contenido, content_type = archivos[nombre]
            if contenido:
                try:
                    guardar_archivo(doc_id, contenido, nombre, content_type)
                    tiene_archivo = True
                except Exception as exc:
                    logger.warning("No se pudo guardar '%s': %s", nombre, exc)

        doc_entry = {
            "id": doc_id, "tramite_id": tramite_id, "nombre": nombre,
            "tipo_detectado": tipo_doc, "validez": "VALIDO",
            "confianza": clf.confianza_nivel, "confianza_score": clf.confianza_score,
            "tiene_archivo": tiene_archivo, "campos_extraidos": campos,
            "justificacion": clf.justificacion or "",
        }
        DOCUMENTOS_CARGA[doc_id] = doc_entry
        tramite.setdefault("documentos", []).append({
            "id": doc_id, "nombre": nombre, "tipo_detectado": tipo_doc,
            "validez": "VALIDO", "confianza": clf.confianza_nivel,
        })
        nuevos_nombres.append(nombre)

    # Acumular identificadores extraídos de los nuevos documentos
    from app.services.registro_tramites import actualizar_identificadores
    mat_nueva, bas_nueva = extraer_identificador("", clasificaciones)
    actualizar_identificadores(tramite, mat_nueva, bas_nueva)

    recotejar_tramite(tramite)

    estado_nuevo = tramite["estado"]
    tramite.setdefault("historial", []).append({
        "momento": ahora,
        "evento": (
            f"Respuesta recibida de {remitente} — "
            f"{len(nuevos_nombres)} documento(s) nuevo(s): {', '.join(nuevos_nombres)}. "
            f"Cotejo actualizado → {estado_nuevo}."
        ),
        "actor": "tyrion",
    })
    logger.info(
        "Trámite %s: %d doc(s) adjuntados desde %s — nuevo estado: %s",
        tramite_id, len(nuevos_nombres), remitente, estado_nuevo,
    )


async def ingestar_documentos(
    clasificaciones: dict,
    crear_tramite_fn: Callable,
    in_reply_to: str | None = None,
    references: str | None = None,
    asunto: str | None = None,
    archivos: dict | None = None,
    doc_ids: dict | None = None,
    matricula_declarada: str | None = None,
    bastidor_declarado: str | None = None,
    remitente: str = "",
    tramite_id_nuevo: str | None = None,
) -> tuple[dict, bool]:
    """Punto único de entrada para ingesta de documentos (email y carga manual).

    1. Extrae mat/bas de clasificaciones (+ declarados desde formulario).
    2. Busca expediente existente (cualquier estado excepto cerrado).
    3a. Si existe → adjunta documentos, acumula identificadores, re-coteja.
    3b. Si no existe → llama a crear_tramite_fn(tramite_id, mat, bas) → registra.
         Sin identificador → estado sin_correlacionar.

    Retorna (tramite, es_nuevo).
    `crear_tramite_fn` puede ser async o sync.
    """
    from app.services.registro_tramites import (
        buscar_expediente, actualizar_identificadores, normalizar_matricula,
        normalizar_bastidor, agregar_tramite,
    )

    # Extraer identificadores de los documentos
    mat, bas = extraer_identificador("", clasificaciones)
    mat = mat or matricula_declarada
    bas = bas or bastidor_declarado

    # Buscar expediente (sin filtro de estado salvo cerrado)
    tramite_existente = buscar_expediente(
        matricula=mat, bastidor=bas,
        in_reply_to=in_reply_to, references=references, asunto=asunto,
    )

    if tramite_existente is not None:
        adjuntar_documentos(
            tramite_existente, clasificaciones, remitente,
            archivos=archivos, doc_ids=doc_ids,
        )
        return tramite_existente, False

    # Crear nuevo expediente
    tid = tramite_id_nuevo or str(uuid4())
    if inspect.iscoroutinefunction(crear_tramite_fn):
        tramite = await crear_tramite_fn(tid, mat, bas)
    else:
        tramite = crear_tramite_fn(tid, mat, bas)

    # Sin identificador extraíble → sin_correlacionar
    if not normalizar_matricula(mat) and not normalizar_bastidor(bas):
        tramite["estado"] = "sin_correlacionar"
        tramite["alerta"] = True

    actualizar_identificadores(tramite, mat, bas)
    agregar_tramite(tramite)
    return tramite, True
