"""
Tests para las validaciones cruzadas multi-documento (cruces.py).

Cubre la matriz §9:
  - cruce_transferencia: bastidor, CET, NIF transmitente
  - cruce_herencia:      causante, titular CTI, bastidor en Anexo 650
  - cruce_matriculacion: bastidor consistente, potencia kW

Clave de cruce primaria = bastidor (VIN), no matrícula.
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

def test_herencia_sin_discrepancias():
    """Todos los campos de herencia consistentes → ok."""
    result = cruce_herencia(
        nombre_causante_defuncion="JUAN GARCIA LOPEZ",
        nombre_causante_650="JUAN GARCIA LOPEZ",
        nombre_titular_cti="JUAN GARCIA LOPEZ",
        bastidor_cti=BASTIDOR_OK,
        bastidor_anexo_650=BASTIDOR_OK,
    )
    assert result.ok


def test_herencia_causante_650_difiere_defuncion_rechazado():
    """Causante del 650 ≠ fallecido en defunción → RECHAZADO (error crítico)."""
    result = cruce_herencia(
        nombre_causante_defuncion="JUAN GARCIA LOPEZ",
        nombre_causante_650="PEDRO MARTINEZ RUIZ",
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "nombre_causante"
    assert disc.severidad == SeveridadCruce.RECHAZADO
    assert result.requiere_revision_manual


def test_herencia_fallecido_no_es_titular_cti_evidencia():
    """Fallecido ≠ titular del CTI → EVIDENCIA (puede ser heredado de tercero)."""
    result = cruce_herencia(
        nombre_causante_defuncion="JUAN GARCIA LOPEZ",
        nombre_causante_650="JUAN GARCIA LOPEZ",
        nombre_titular_cti="MARIA PEREZ SANTOS",
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "titular_vehiculo"
    assert disc.severidad == SeveridadCruce.EVIDENCIA


def test_herencia_bastidor_no_en_anexo_650_rechazado():
    """El vehículo no figura en el Anexo 650 → RECHAZADO."""
    result = cruce_herencia(
        nombre_causante_defuncion="JUAN GARCIA LOPEZ",
        nombre_causante_650="JUAN GARCIA LOPEZ",
        nombre_titular_cti="JUAN GARCIA LOPEZ",
        bastidor_cti=BASTIDOR_OK,
        bastidor_anexo_650=BASTIDOR_OTRO,
    )
    assert not result.ok
    disc = result.discrepancias[0]
    assert disc.campo == "bastidor"
    assert disc.severidad == SeveridadCruce.RECHAZADO


def test_herencia_multiples_discrepancias():
    """Varias discrepancias simultáneas: la severidad máxima es RECHAZADO."""
    result = cruce_herencia(
        nombre_causante_defuncion="JUAN GARCIA LOPEZ",
        nombre_causante_650="PEDRO MARTINEZ RUIZ",   # RECHAZADO
        nombre_titular_cti="MARIA PEREZ SANTOS",      # EVIDENCIA
        bastidor_cti=BASTIDOR_OK,
        bastidor_anexo_650=BASTIDOR_OTRO,              # RECHAZADO
    )
    assert len(result.discrepancias) == 3
    assert result.severidad_maxima == SeveridadCruce.RECHAZADO


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
