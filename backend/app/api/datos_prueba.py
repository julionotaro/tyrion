"""
Datos de prueba para la Pantalla Control y el Split-view documental.

Se usan cuando USE_DATOS_PRUEBA=true en config (sin BD real conectada).
Cubren los 6 macro-estados para poder ver la pantalla completa desde el primer día.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# Hora base para que los datos de prueba tengan tiempos relativos realistas
_AHORA = datetime(2026, 6, 15, 9, 0, 0)


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
        "nombre": "permiso.pdf",
        "tipo_detectado": "permiso_circulacion",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.95,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "matricula",    "valor": "5678 DEF",   "estado": "valido"},
            {"campo": "titular",      "valor": "Ana Martín", "estado": "valido"},
            {"campo": "marca_modelo", "valor": "VW Golf",    "estado": "valido"},
            {"campo": "fecha_matriculacion", "valor": "02/07/2021", "estado": "valido"},
        ],
        "justificacion": "Documento DGT correcto. Todos los campos coinciden con el trámite.",
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
    "doc-004": {
        "id": "doc-004",
        "tramite_id": "t-002",
        "nombre": "dni_comprador.pdf",
        "tipo_detectado": "dni",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.98,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "nombre",    "valor": "Ana Martín López", "estado": "valido"},
            {"campo": "dni",       "valor": "12345678A",        "estado": "valido"},
            {"campo": "caducidad", "valor": "01/01/2030",       "estado": "valido"},
        ],
        "justificacion": "DNI vigente, datos legibles.",
    },
    "doc-005": {
        "id": "doc-005",
        "tramite_id": "t-003",
        # Caso de error: envían CTI en lugar de permiso_circulacion
        "nombre": "cti.pdf",
        "tipo_detectado": "cti",
        "validez": "EVIDENCIA_COMPATIBLE",
        "confianza": "ALTA",
        "confianza_score": 0.93,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "matricula",   "valor": "9012 GHI",  "estado": "valido"},
            {"campo": "resultado_itv","valor": "FAVORABLE", "estado": "valido"},
            {"campo": "fecha_itv",   "valor": "10/03/2026", "estado": "valido"},
            # Campo que falta respecto al permiso requerido:
            {"campo": "titular",     "valor": "(no visible en CTI)", "estado": "evidencia"},
        ],
        "justificacion": (
            "Se detectó CTI/ficha ITV, no el Permiso de Circulación requerido. "
            "Son documentos relacionados pero no intercambiables (regla de oro). "
            "Se solicitó a la gestoría el documento correcto."
        ),
    },
    "doc-006": {
        "id": "doc-006",
        "tramite_id": "t-003",
        "nombre": "dni.pdf",
        "tipo_detectado": "dni",
        "validez": "VALIDO",
        "confianza": "ALTA",
        "confianza_score": 0.96,
        "tiene_archivo": False,
        "campos_extraidos": [
            {"campo": "nombre",    "valor": "Carlos Ruiz", "estado": "valido"},
            {"campo": "dni",       "valor": "87654321B",   "estado": "valido"},
            {"campo": "caducidad", "valor": "15/08/2028",  "estado": "valido"},
        ],
        "justificacion": "DNI correcto y vigente.",
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
            {"id": "doc-002", "nombre": "permiso.pdf",
             "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": "doc-003", "nombre": "modelo620.pdf",
             "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"id": "doc-004", "nombre": "dni_comprador.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(45), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(44), "evento": "3 documentos clasificados", "actor": "tyrion"},
        ],
        "avisos_pendientes": [],
    },
    {
        "id": "t-003",
        "tipo": "TRANSFERENCIA",
        "matricula": "9012 GHI",
        "bastidor": None,
        "gestoria": "Gestoria Ruiz",
        "gestoria_email": "ruiz@gestorias.es",
        "estado": "pendiente_gestoria",
        "fecha_entrada": _hace(90),
        "alerta": True,
        "documentos": [
            {"id": "doc-005", "nombre": "cti.pdf",
             "tipo_detectado": "cti",
             "validez": "EVIDENCIA_COMPATIBLE", "confianza": "ALTA"},
            {"id": "doc-006", "nombre": "dni.pdf",
             "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
        ],
        "historial": [
            {"momento": _hace(90), "evento": "Email recibido", "actor": "tyrion"},
            {"momento": _hace(89), "evento": "CTI recibido en lugar de permiso_circulacion",
             "actor": "tyrion"},
            {"momento": _hace(89), "evento": "aviso_1 preparado para ruiz@gestorias.es",
             "actor": "tyrion"},
            {"momento": _hace(59), "evento": "aviso_2 preparado (sin respuesta al aviso_1)",
             "actor": "tyrion"},
        ],
        "avisos_pendientes": [
            {"tipo": "aviso_2", "enviado_at": _hace(59), "requisito": "permiso_circulacion"},
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
}
