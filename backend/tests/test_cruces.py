"""
Tests para las validaciones cruzadas multi-documento (cruces.py).

Cubre la matriz §9:
  - cruce_transferencia: bastidor, CET, NIF transmitente
  - cruce_herencia:      matrícula como clave principal; DNI para identidad;
                         bastidor validado solo en anexo_650
  - cruce_matriculacion: bastidor consistente, potencia kW
"""
import pytest

from app.services.cruces import (
    SeveridadCruce,
    cruce_herencia,
    cruce_matriculacion,
    cruce_transferencia,
)


BASTIDOR_OK = "VF3XXXXXX12345678"
BASTIDOR_OTRO = "VF3XXXXXX99999999"


# ── cruce_transferencia ───────────────────────────────────────────────────────

def test_transferencia_sin_discrepancias():
    """Todo consistente: bastidores iguales, CETs dentro de tolerancia, mismo NIF."""
    result = cruce_transferencia(
        bastidor_permiso=BASTIDOR_OK,
        bastidor_cti=BASTIDOR_OK,
        bastidor_620=BASTIDOR_OK,
        cet_cti=10000.0,
        cet_620=10200.0,   # 2% de diferencia — dentro de 5% por defecto
        nif_titular_permiso="12345678A",
        nif_transmitente_dni="12345678A",
    )
    assert result.ok
    assert result.severidad_maxima == SeveridadCruce.OK
    assert not result.requiere_revision_manual


def test_transferencia_bastidor_permiso_cti_difieren_rechazado():
    """Bastidor diferente entre permiso y CTI → RECHAZADO (fraude potencial)."""
    result = cruce_transferencia(
        bastidor_permiso=BASTIDOR_OK,
        bastidor_cti=BASTIDOR_OTRO,
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "bastidor"
    assert disc.severidad == SeveridadCruce.RECHAZADO
    assert result.requiere_revision_manual


def test_transferencia_bastidor_permiso_620_difieren_rechazado():
    """Bastidor diferente entre permiso y 620 → RECHAZADO."""
    result = cruce_transferencia(
        bastidor_permiso=BASTIDOR_OK,
        bastidor_620=BASTIDOR_OTRO,
    )
    assert not result.ok
    assert any(d.campo == "bastidor" and d.doc_b == "modelo_620" for d in result.discrepancias)
    assert result.severidad_maxima == SeveridadCruce.RECHAZADO


def test_transferencia_cet_fuera_tolerancia_evidencia():
    """CET del CTI y el 620 difieren >5%: EVIDENCIA (pedir justificación, no admin)."""
    result = cruce_transferencia(
        cet_cti=10000.0,
        cet_620=9400.0,    # 6% de diferencia — fuera de tolerancia
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "cet"
    assert disc.severidad == SeveridadCruce.EVIDENCIA
    assert not result.requiere_revision_manual   # EVIDENCIA, no admin todavía


def test_transferencia_cet_dentro_tolerancia_ok():
    """CET difiere 3% (< 5%): dentro de tolerancia, sin discrepancia."""
    result = cruce_transferencia(
        cet_cti=10000.0,
        cet_620=9700.0,
    )
    assert result.ok


def test_transferencia_nif_transmitente_difiere_evidencia():
    """Titular del permiso ≠ NIF del DNI del transmitente → EVIDENCIA."""
    result = cruce_transferencia(
        nif_titular_permiso="12345678A",
        nif_transmitente_dni="87654321Z",
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "nif_transmitente"
    assert disc.severidad == SeveridadCruce.EVIDENCIA


def test_transferencia_bastidores_vacios_no_critica():
    """Sin bastidores proporcionados: no hay discrepancias (datos no disponibles)."""
    result = cruce_transferencia()
    assert result.ok


def test_transferencia_bastidor_normalizado():
    """Los bastidores se normalizan (mayúsculas, sin espacios)."""
    result = cruce_transferencia(
        bastidor_permiso="vf3xxxxxx12345678",
        bastidor_cti=" VF3XXXXXX12345678 ",
    )
    assert result.ok


# ── cruce_herencia ────────────────────────────────────────────────────────────
# Caso real: González Fernández
# CTI: matricula=5042HZM, dni_transmitente=14958073T, dni_adquirente=35306584C
# Declaración responsable: matricula=5042-HZM, dni=35306584C
# Modelo 650: dni_causante=14958073T, dni_sujeto_pasivo=35306584C
# Anexo 650: matricula=5042HZM, bastidor=JYA5J09200002507G
# Cert defunción: dni_fallecido=14958073T

_MAT_CTI  = "5042HZM"
_MAT_DECL = "5042-HZM"   # guión — se normaliza
_MAT_ANEXO = "5042HZM"
_DNI_CAUSANTE   = "14958073T"
_DNI_HEREDERO   = "35306584C"
_BASTIDOR_REAL  = "JYA5J09200002507G"


def test_herencia_caso_gonzalez_sin_discrepancias():
    """Caso real González Fernández — todo consistente → ok."""
    result = cruce_herencia(
        matricula_cti=_MAT_CTI,
        matricula_declaracion=_MAT_DECL,
        matricula_anexo_650=_MAT_ANEXO,
        dni_causante_defuncion=_DNI_CAUSANTE,
        dni_causante_650=_DNI_CAUSANTE,
        dni_transmitente_cti=_DNI_CAUSANTE,
        dni_heredero_declaracion=_DNI_HEREDERO,
        dni_heredero_650=_DNI_HEREDERO,
        dni_adquirente_cti=_DNI_HEREDERO,
        bastidor_anexo_650=_BASTIDOR_REAL,
    )
    assert result.ok
    assert result.severidad_maxima == SeveridadCruce.OK


def test_herencia_matricula_divergente_cti_declaracion_evidencia():
    """Matrícula CTI ≠ declaración responsable → EVIDENCIA."""
    result = cruce_herencia(
        matricula_cti="5042HZM",
        matricula_declaracion="9999ABC",
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "matricula"
    assert disc.severidad == SeveridadCruce.EVIDENCIA


def test_herencia_matricula_divergente_cti_anexo_evidencia():
    """Matrícula CTI ≠ anexo_650 → EVIDENCIA."""
    result = cruce_herencia(
        matricula_cti="5042HZM",
        matricula_anexo_650="9999ABC",
    )
    assert not result.ok
    assert any(d.campo == "matricula" for d in result.discrepancias)
    assert result.severidad_maxima == SeveridadCruce.EVIDENCIA


def test_herencia_dni_causante_defuncion_650_difieren_rechazado():
    """DNI del fallecido (defunción) ≠ DNI causante (650) → RECHAZADO (error crítico)."""
    result = cruce_herencia(
        dni_causante_defuncion="14958073T",
        dni_causante_650="99999999Z",
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "dni_causante"
    assert disc.severidad == SeveridadCruce.RECHAZADO
    assert result.requiere_revision_manual


def test_herencia_dni_causante_defuncion_cti_difieren_evidencia():
    """DNI fallecido ≠ DNI transmitente CTI → EVIDENCIA."""
    result = cruce_herencia(
        dni_causante_defuncion="14958073T",
        dni_causante_650="14958073T",      # 650 ok
        dni_transmitente_cti="99999999Z",  # CTI difiere
    )
    assert not result.ok
    assert any(d.campo == "dni_causante" and d.severidad == SeveridadCruce.EVIDENCIA
               for d in result.discrepancias)


def test_herencia_bastidor_ausente_anexo_evidencia():
    """Sin bastidor en anexo_650 → EVIDENCIA (campo faltante)."""
    result = cruce_herencia(bastidor_anexo_650="")
    assert not result.ok
    assert any(d.campo == "bastidor" and d.doc_a == "anexo_650" for d in result.discrepancias)
    assert result.severidad_maxima == SeveridadCruce.EVIDENCIA


def test_herencia_sin_datos_solo_bastidor_ausente():
    """Sin datos: solo se activa el aviso de bastidor ausente en anexo (campo obligatorio)."""
    result = cruce_herencia()
    assert not result.ok
    assert len(result.discrepancias) == 1
    assert result.discrepancias[0].campo == "bastidor"
    assert result.severidad_maxima == SeveridadCruce.EVIDENCIA


# ── cruce_matriculacion ───────────────────────────────────────────────────────

def test_matriculacion_sin_discrepancias():
    """Todos los bastidores iguales, potencia consistente."""
    result = cruce_matriculacion(
        bastidor_solicitud=BASTIDOR_OK,
        bastidor_ficha_tecnica=BASTIDOR_OK,
        bastidor_ivtm=BASTIDOR_OK,
        bastidor_impuesto_matriculacion=BASTIDOR_OK,
        potencia_kw_ficha=75.0,
        potencia_kw_ivtm=75.0,
    )
    assert result.ok


def test_matriculacion_bastidor_ficha_difiere_rechazado():
    """Bastidor en ficha técnica ≠ solicitud → RECHAZADO."""
    result = cruce_matriculacion(
        bastidor_solicitud=BASTIDOR_OK,
        bastidor_ficha_tecnica=BASTIDOR_OTRO,
        bastidor_ivtm=BASTIDOR_OK,
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "bastidor"
    assert disc.doc_b == "ficha_tecnica"
    assert disc.severidad == SeveridadCruce.RECHAZADO


def test_matriculacion_bastidor_ivtm_difiere_rechazado():
    """Bastidor en IVTM ≠ solicitud → RECHAZADO."""
    result = cruce_matriculacion(
        bastidor_solicitud=BASTIDOR_OK,
        bastidor_ficha_tecnica=BASTIDOR_OK,
        bastidor_ivtm=BASTIDOR_OTRO,
    )
    assert not result.ok
    assert any(d.doc_b == "ivtm" for d in result.discrepancias)


def test_matriculacion_potencia_difiere_evidencia():
    """Potencia en ficha ≠ potencia en IVTM → EVIDENCIA (base de cálculo incorrecta)."""
    result = cruce_matriculacion(
        bastidor_solicitud=BASTIDOR_OK,
        bastidor_ficha_tecnica=BASTIDOR_OK,
        bastidor_ivtm=BASTIDOR_OK,
        potencia_kw_ficha=75.0,
        potencia_kw_ivtm=100.0,
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "potencia_kw"
    assert disc.severidad == SeveridadCruce.EVIDENCIA


def test_matriculacion_potencia_dentro_tolerancia_ok():
    """Diferencia de 0.3 kW (< 0.5 umbral): dentro de tolerancia."""
    result = cruce_matriculacion(
        bastidor_solicitud=BASTIDOR_OK,
        potencia_kw_ficha=75.0,
        potencia_kw_ivtm=75.3,
    )
    assert result.ok


def test_matriculacion_sin_datos_no_critica():
    """Sin datos proporcionados: sin discrepancias (datos no disponibles)."""
    result = cruce_matriculacion()
    assert result.ok


def test_matriculacion_bastidor_normalizado():
    """Los bastidores se normalizan antes de comparar."""
    result = cruce_matriculacion(
        bastidor_solicitud="vf3xxxxxx12345678",
        bastidor_ficha_tecnica="VF3XXXXXX12345678",
    )
    assert result.ok
