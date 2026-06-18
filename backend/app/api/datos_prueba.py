"""
Datos de prueba para la Pantalla Control y el Split-view documental.

Se usan cuando USE_DATOS_PRUEBA=true en config (sin BD real conectada).
Cubren los 6 macro-estados para poder ver la pantalla completa desde el primer día.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# Hora base para que los datos de prueba tengan tiempos relativos realistas
_AHORA = datetime.now().replace(second=0, microsecond=0)


def _hace(minutos: int) -> str:
    return (_AHORA - timedelta(minutes=minutos)).isoformat()


# Catálogo de documentos simulados con campos extraídos por tipo.
# Cada documento tiene un id único, campos extraídos y resultado de cotejo.
DOCUMENTOS_PRUEBA: dict[str, dict[str, Any]] = {
    "doc-001": {
        "id": "doc-001",
        "tramite_id": "t-001",
        "nombre": "permiso.pdf",
        "tipo_detectado": "permiso_circulacion",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.97,
        # Simulación de PDF: URL de un PDF de muestra público
        "archivo_url": "/static/muestra_permiso.pdf",
        "tiene_archivo": False,  # en pruebas no hay PDF real
        "campos_extraidos": [
            {"campo": "matricula",          "valor": "1234 ABC",     "estado": "valido"},
            {"campo": "titular",            "valor": "Juan García",  "estado": "valido"},
            {"campo": "marca_modelo",       "valor": "SEAT Ibiza",   "estado": "valido"},
            {"campo": "fecha_matriculacion","valor": "15/03/2018",   "estado": "valido"},
            {"campo": "num_bastidor",       "valor": "VS6RFD000X1234","estado": "valido"},
        ],
        "justificacion": "Encabezado 'Permiso de Circulación' visible. Todos los campos presentes.",
    },
    "doc-002": {
        "id": "doc-002",
        "tramite_id": "t-002",
        "nombre": "cti.pdf",
        "tipo_detectado": "cti",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.95,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "matricula", "valor": "5678 DEF",   "estado": "valido"},
            {"campo": "titular",   "valor": "Ana Martín", "estado": "valido"},
            {"campo": "bastidor",  "valor": "WVWZZZ1KZAW123456", "estado": "valido"},
            {"campo": "cet",       "valor": "CET-2026-002",      "estado": "valido"},
        ],
        "justificacion": "CTI (Cambio de Titularidad) correcto. Todos los campos presentes.",
    },
    "doc-003": {
        "id": "doc-003",
        "tramite_id": "t-002",
        "nombre": "modelo620.pdf",
        "tipo_detectado": "modelo_620",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.91,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "transmitente",  "valor": "Pedro Ruiz",     "estado": "valido"},
            {"campo": "adquirente",    "valor": "Ana Martín",     "estado": "valido"},
            {"campo": "importe",       "valor": "8.500 €",        "estado": "valido"},
            {"campo": "fecha_liquidacion", "valor": "14/06/2026", "estado": "valido"},
            {"campo": "numero_modelo", "valor": "620",            "estado": "valido"},
        ],
        "justificacion": "Formulario 620 con todos los campos de liquidación presentes.",
    },
    "doc-005": {
        "id": "doc-005",
        "tramite_id": "t-003",
        "nombre": "decl_responsable.pdf",
        "tipo_detectado": "declaracion_responsable_fallecimiento",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.95,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "nombre",    "valor": "Carlos Ruiz Fernández", "estado": "valido"},
            {"campo": "dni",       "valor": "87654321B",              "estado": "valido"},
            {"campo": "matricula", "valor": "9012 GHI",               "estado": "valido"},
        ],
        "justificacion": (
            "Declaración responsable de persona física para cambio de titularidad por fallecimiento. "
            "Nombre, DNI y matrícula presentes y legibles. Documento VÁLIDO."
        ),
    },
    "doc-005b": {
        "id": "doc-005b",
        "tramite_id": "t-003",
        "nombre": "modelo_650.pdf",
        "tipo_detectado": "modelo_650",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.93,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "causante", "valor": "Pedro Ruiz García",     "estado": "valido"},
            {"campo": "heredero", "valor": "Carlos Ruiz Fernández", "estado": "valido"},
            {"campo": "importe",  "valor": "1.250 €",               "estado": "valido"},
        ],
        "justificacion": "Modelo 650 (Impuesto Sucesiones) con causante y heredero identificados.",
    },
    "doc-005c": {
        "id": "doc-005c",
        "tramite_id": "t-003",
        "nombre": "anexo_650.pdf",
        "tipo_detectado": "anexo_650",
        "validez": "EVIDENCIA_COMPATIBLE",
        "confianza": "ALTA",
        "confianza_score": 0.91,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "bastidor",       "valor": "VS6RFD000X9999", "estado": "rechazado"},
            {"campo": "valor_vehiculo", "valor": "12.000 €",       "estado": "valido"},
        ],
        "justificacion": (
            "Anexo 650 recibido. ALERTA: el bastidor en el Anexo (VS6RFD000X9999) "
            "no coincide con el bastidor del trámite (VS6RFD000X1234). "
            "Diferencia en últimos 4 dígitos: 9999 ≠ 1234. "
            "Se ha solicitado corrección a la gestoría."
        ),
    },
    "doc-007": {
        "id": "doc-007",
        "tramite_id": "t-008",
        # Caso de rechazo: envían hoja_caja donde se pide permiso
        "nombre": "hoja_caja.pdf",
        "tipo_detectado": "hoja_caja",
        "validez": "RECHAZADO",
        "confianza": "ALTA",
        "confianza_score": 0.94,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "tipo_documento", "valor": "Hoja de caja diaria", "estado": "rechazado"},
            {"campo": "gestoria",       "valor": "Gestoria Ruiz",       "estado": "rechazado"},
            {"campo": "fecha",          "valor": "15/06/2026",          "estado": "rechazado"},
        ],
        "justificacion": (
            "Documento identificado como hoja_caja. "
            "No corresponde al requisito permiso_circulacion ni a ningún tipo relacionado. "
            "Caso escalado al administrativo."
        ),
    },
    "doc-008": {
        "id": "doc-008",
        "tramite_id": "t-008",
        "nombre": "dni.pdf",
        "tipo_detectado": "dni",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.97,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "nombre",    "valor": "María Ruiz", "estado": "valido"},
            {"campo": "dni",       "valor": "11223344C",  "estado": "valido"},
            {"campo": "caducidad", "valor": "30/06/2027", "estado": "valido"},
        ],
        "justificacion": "DNI correcto y vigente.",
    },
}

# Índice: tramite_id → lista de doc_ids
_DOC_POR_TRAMITE: dict[str, list[str]] = {}
for _doc_id, _doc in DOCUMENTOS_PRUEBA.items():
    _DOC_POR_TRAMITE.setdefault(_doc["tramite_id"], []).append(_doc_id)


def docs_de_tramite(tramite_id: str) -> list[dict[str, Any]]:
    return [DOCUMENTOS_PRUEBA[d] for d in _DOC_POR_TRAMITE.get(tramite_id, [])]


# 8 trámites cubriendo todos los macro-estados
TRAMITES_PRUEBA: list[dict[str, Any]] = [
    {
        "id": "t-001",
        "tipo": "TRANSFERENCIA",
        "matricula": "1234 ABC",
        "bastidor": None,
        "gestoria": "Gestoria López",
        "gestoria_email": "lopez@gestorias.es",
        "estado": "recibido",
        "fecha_entrada": _hace(5),
        "alerta": False,
        "documentos": [
            {"id": "doc-001", "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(5), "evento": "Email recibido de lopez@gestorias.es",
             "actor": "tyrion"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-002",
        "tipo": "TRANSFERENCIA",
        "matricula": "5678 DEF",
        "bastidor": None,
        "gestoria": "Gestoria Martín",
        "gestoria_email": "martin@gestorias.es",
        "estado": "en_revision",
        "fecha_entrada": _hace(45),
        "alerta": False,
        "documentos": [
            {"id": "doc-002", "nombre": "cti.pdf",
             "tipo_detectado": "cti",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": "doc-003", "nombre": "modelo620.pdf",
             "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(45), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(44), "evento": "2 documentos clasificados (versión acotada)",
             "actor": "tyrion"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-003",
        "tipo": "TRANSFERENCIA",
        "subtipo": "herencia",
        "matricula": "9012 GHI",
        "bastidor": "VS6RFD000X1234",
        "gestoria": "Gestoria Ruiz",
        "gestoria_email": "ruiz@gestorias.es",
        "estado": "pendiente_gestoria",
        "fecha_entrada": _hace(90),
        "alerta": True,
        "documentos": [
            {"id": "doc-005",  "nombre": "decl_responsable.pdf",
             "tipo_detectado": "declaracion_responsable_fallecimiento",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": "doc-005b", "nombre": "modelo_650.pdf",
             "tipo_detectado": "modelo_650",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": "doc-005c", "nombre": "anexo_650.pdf",
             "tipo_detectado": "anexo_650",
             "validez": "EVIDENCIA_COMPATIBLE", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(90), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(89),
             "evento": "Declaración responsable + modelo 650 + anexo 650 clasificados",
             "actor": "tyrion"},
            {"momento": _hace(89),
             "evento": "⚠ Bastidor en Anexo 650 (X9999) no coincide con bastidor del trámite (X1234) — aviso_1 preparado para ruiz@gestorias.es",
             "actor": "tyrion"},
        ],
        "avisos_pendientes": [
            {"tipo": "aviso_1", "enviado_at": _hace(89), "requisito": "anexo_650"},
        ],
    },
    {
        "id": "t-004",
        "tipo": "BAJA",
        "matricula": "3456 JKL",
        "bastidor": None,
        "gestoria": "Gestoria Fernández",
        "gestoria_email": "fernandez@gestorias.es",
        "estado": "pendiente_gestoria",
        "fecha_entrada": _hace(25),
        "alerta": False,
        "documentos": [
            {"id": None, "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(25), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(24), "evento": "Falta dni — aviso_1 preparado", "actor": "tyrion"},
        ],
        "avisos_pendientes": [
            {"tipo": "aviso_1", "enviado_at": _hace(24), "requisito": "dni"},
        ],
    },
    {
        "id": "t-005",
        "tipo": "MATRICULACION",
        "matricula": None,
        "bastidor": "VF1RFD00060123456",
        "gestoria": "Gestoria López",
        "gestoria_email": "lopez@gestorias.es",
        "estado": "listo_dgt",
        "fecha_entrada": _hace(120),
        "alerta": False,
        "documentos": [
            {"id": None, "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "ficha.pdf",
             "tipo_detectado": "ficha_tecnica",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "justificante.pdf",
             "tipo_detectado": "justificante_pago",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "dni.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(120), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(118), "evento": "4 documentos VALIDOS — expediente completo",
             "actor": "tyrion"},
            {"momento": _hace(100), "evento": "Marcado listo para presentar a DGT",
             "actor": "admin"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-006",
        "tipo": "TRANSFERENCIA",
        "matricula": "7890 MNO",
        "bastidor": None,
        "gestoria": "Gestoria Sánchez",
        "gestoria_email": "sanchez@gestorias.es",
        "estado": "en_cadeteria",
        "fecha_entrada": _hace(180),
        "alerta": False,
        "documentos": [
            {"id": None, "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "modelo620.pdf",
             "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "dni.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "contrato.pdf",
             "tipo_detectado": "contrato_compraventa",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(180), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(160), "evento": "Expediente completo", "actor": "tyrion"},
            {"momento": _hace(140), "evento": "Enviado a cadetería para presentar en DGT",
             "actor": "admin"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-007",
        "tipo": "TRANSFERENCIA",
        "matricula": "2345 PQR",
        "bastidor": None,
        "gestoria": "Gestoria Martín",
        "gestoria_email": "martin@gestorias.es",
        "estado": "cerrado",
        "fecha_entrada": _hace(300),
        "alerta": False,
        "num_comprobante_dgt": "DGT-2026-00123",
        "documentos": [
            {"id": None, "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "modelo620.pdf",
             "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "dni.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": None, "nombre": "contrato.pdf",
             "tipo_detectado": "contrato_compraventa",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(300), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(280), "evento": "Expediente completo", "actor": "tyrion"},
            {"momento": _hace(240), "evento": "Presentado en DGT — comprobante DGT-2026-00123",
             "actor": "admin"},
            {"momento": _hace(60), "evento": "Permisos impresos recibidos — FINALIZADO",
             "actor": "admin"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-008",
        "tipo": "BAJA",
        "matricula": "6789 STU",
        "bastidor": None,
        "gestoria": "Gestoria Ruiz",
        "gestoria_email": "ruiz@gestorias.es",
        "estado": "pendiente_gestoria",
        "fecha_entrada": _hace(75),
        "alerta": True,
        "documentos": [
            {"id": "doc-007", "nombre": "hoja_caja.pdf",
             "tipo_detectado": "hoja_caja",
             "validez": "RECHAZADO", "confianza": "ALTA"},
            {"id": "doc-008", "nombre": "dni.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(75), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(74), "evento": "hoja_caja RECHAZADA (no es permiso_circulacion)",
             "actor": "tyrion"},
            {"momento": _hace(74), "evento": "Escalado al administrativo", "actor": "tyrion"},
        ],
        "avisos_pendientes": [
            {"tipo": "escalado", "enviado_at": _hace(74), "requisito": "permiso_circulacion"},
        ],
    },
]

MACRO_ESTADOS = ["recibido", "en_revision", "pendiente_gestoria",
                 "listo_dgt", "en_cadeteria", "cerrado"]

ETIQUETAS_ESTADO = {
    "recibido":           "Recibido",
    "en_revision":        "En revisión",
    "pendiente_gestoria": "Pendiente gestoría",
    "listo_dgt":          "Listo DGT",
    "en_cadeteria":       "En cadetería",
    "cerrado":            "Cerrado",
    "pendiente_jefatura": "Pendiente Jefatura",
}

# ── Planilla del día simulada ─────────────────────────────────────────────────
# 8 trámites planificados que corresponden a los 8 trámites de prueba.
# + 1 sin documentación (email aún no recibido)
# + 1 email simulado sin match en planilla (bastidor desconocido)

PLANILLA_DIA_PRUEBA: dict[str, Any] = {
    "fecha": "2026-06-15",
    "tipo": "TRANSMISIONES",
    "fuente": "tempus",
    "tramites_planificados": [
        {
            "id": "tp-001",
            "bastidor": "VS6RFD000X1234",
            "matricula": "1234ABC",
            "nif_adquirente": "12345678A",
            "num_expediente": "EXP-2026-001",
            "nombre_titular": "Juan García López",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "con_documentacion",
            "tramite_id": "t-001",
        },
        {
            "id": "tp-002",
            "bastidor": "WVWZZZ1KZAW123456",
            "matricula": "5678DEF",
            "nif_adquirente": "87654321B",
            "num_expediente": "EXP-2026-002",
            "nombre_titular": "Ana Martín Pérez",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "con_documentacion",
            "tramite_id": "t-002",
        },
        {
            "id": "tp-003",
            "bastidor": "VF3XXXXXX12345678",
            "matricula": "9012GHI",
            "nif_adquirente": "11223344C",
            "num_expediente": "EXP-2026-003",
            "nombre_titular": "Carlos Ruiz Fernández",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "con_documentacion",
            "tramite_id": "t-003",
        },
        {
            "id": "tp-004",
            "bastidor": "ZFA19800000537243",
            "matricula": "3456JKL",
            "nif_adquirente": "55667788D",
            "num_expediente": "EXP-2026-004",
            "nombre_titular": "María López Sanz",
            "tipo_tramite": "MATRICULACION",
            "estado": "con_documentacion",
            "tramite_id": "t-004",
        },
        {
            "id": "tp-005",
            "bastidor": "VSSZZZ6KZHR123456",
            "matricula": "7890MNO",
            "nif_adquirente": "99887766E",
            "num_expediente": "EXP-2026-005",
            "nombre_titular": "Pedro Sánchez Torres",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "con_documentacion",
            "tramite_id": "t-005",
        },
        {
            "id": "tp-006",
            "bastidor": "TMBJF7NE5HJ123456",
            "matricula": "2345PQR",
            "nif_adquirente": "44556677F",
            "num_expediente": "EXP-2026-006",
            "nombre_titular": "Laura González Vega",
            "tipo_tramite": "BAJA",
            "estado": "con_documentacion",
            "tramite_id": "t-006",
        },
        {
            "id": "tp-007",
            "bastidor": "WBA3B31090F123456",
            "matricula": "6789STU",
            "nif_adquirente": "33445566G",
            "num_expediente": "EXP-2026-007",
            "nombre_titular": "Antonio Díaz Morales",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "escalado",
            "tramite_id": "t-007",
        },
        {
            "id": "tp-008",
            "bastidor": "1HGCM82633A123456",
            "matricula": "0123VWX",
            "nif_adquirente": "22334455H",
            "num_expediente": "EXP-2026-008",
            "nombre_titular": "Isabel Romero Castro",
            "tipo_tramite": "MATRICULACION",
            "estado": "con_documentacion",
            "tramite_id": "t-008",
        },
        # Trámite planificado SIN email recibido (sin_documentacion)
        {
            "id": "tp-009",
            "bastidor": "SB1BA4BE50E123456",
            "matricula": "4567YZA",
            "nif_adquirente": "11112222I",
            "num_expediente": "EXP-2026-009",
            "nombre_titular": "Roberto Fernández Gil",
            "tipo_tramite": "TRANSFERENCIA",
            "estado": "sin_documentacion",
            "tramite_id": None,
        },
    ],
    # Email simulado que llegó pero NO tiene fila en la planilla
    "emails_sin_match": [
        {
            "message_id": "sin-match-001@gestorias.es",
            "remitente": "nueva@gestorias.es",
            "asunto": "Documentación trámite XYZ",
            "bastidor_detectado": "XXXXXXXXXXXXXXX99",
            "matricula_detectada": "9999ZZZ",
            "recibido_at": _hace(20),
        },
    ],
}


def planilla_prueba_como_objeto():
    """Devuelve la planilla de prueba como objeto PlanillaDia (para tests y pipeline)."""
    from datetime import date
    from app.services.ingesta_planilla import PlanillaDia, TipoPlanilla, TramitePlanificado, EstadoTramitePlanificado

    tramites = []
    for tp in PLANILLA_DIA_PRUEBA["tramites_planificados"]:
        tramites.append(TramitePlanificado(
            bastidor=tp["bastidor"],
            matricula=tp["matricula"],
            nif_adquirente=tp["nif_adquirente"],
            num_expediente=tp["num_expediente"],
            nombre_titular=tp["nombre_titular"],
            tipo_tramite=tp["tipo_tramite"],
            estado=EstadoTramitePlanificado(tp["estado"]),
            tramite_id=tp.get("tramite_id"),
        ))
    return PlanillaDia(
        fecha=date(2026, 6, 15),
        tipo=TipoPlanilla.TRANSMISIONES,
        fuente="tempus",
        tramites=tramites,
    )
