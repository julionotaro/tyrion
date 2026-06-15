"""
Datos de prueba para la Pantalla Control.

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
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
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
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "modelo620.pdf", "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "dni_comprador.pdf", "tipo_detectado": "dni",
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
        "alerta": True,  # lleva 90 min sin resolverse
        "documentos": [
            {"nombre": "cti.pdf", "tipo_detectado": "cti",
             "validez": "EVIDENCIA_COMPATIBLE", "confianza": "ALTA"},
            {"nombre": "dni.pdf", "tipo_detectado": "dni",
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
        "alerta": False,  # solo 25 min, dentro del SLA
        "documentos": [
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
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
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "ficha.pdf", "tipo_detectado": "ficha_tecnica",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "justificante.pdf", "tipo_detectado": "justificante_pago",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "dni.pdf", "tipo_detectado": "dni",
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
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "modelo620.pdf", "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "dni.pdf", "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "contrato.pdf", "tipo_detectado": "contrato_compraventa",
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
            {"nombre": "permiso.pdf", "tipo_detectado": "permiso_circulacion",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "modelo620.pdf", "tipo_detectado": "modelo_620",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "dni.pdf", "tipo_detectado": "dni",
             "validez": "VALIDO", "confianza": "ALTA"},
            {"nombre": "contrato.pdf", "tipo_detectado": "contrato_compraventa",
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
        "alerta": True,  # escalado al admin por documento rechazado
        "documentos": [
            {"nombre": "hoja_caja.pdf", "tipo_detectado": "hoja_caja",
             "validez": "RECHAZADO", "confianza": "ALTA"},
            {"nombre": "dni.pdf", "tipo_detectado": "dni",
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
