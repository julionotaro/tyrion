"""
Tests: CAMPOS_REQUERIDOS cubre todos los valores del enum TipoDocumento.
"""
from app.services.catalogo_documental import (
    TipoDocumento, CAMPOS_REQUERIDOS, campos_requeridos, evaluar_completitud_extraccion,
)


def test_todos_los_tipos_tienen_entrada():
    """Cada miembro del enum TipoDocumento debe tener entrada en CAMPOS_REQUERIDOS."""
    faltantes = [t for t in TipoDocumento if t not in CAMPOS_REQUERIDOS]
    assert not faltantes, f"Tipos sin entrada en CAMPOS_REQUERIDOS: {faltantes}"


def test_helper_campos_requeridos():
    # CTI: identidad por DNI (no por nombre/titular); bastidor removido (no figura en herencia)
    assert campos_requeridos(TipoDocumento.CTI) == ["matricula", "dni_adquirente", "dni_transmitente", "cet"]
    assert campos_requeridos(TipoDocumento.DESCONOCIDO) == []


def test_evaluar_completo():
    datos = {"matricula": "5042HZM", "dni_adquirente": "35306584C", "dni_transmitente": "14958073T", "cet": "CET123"}
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is True
    assert faltantes == []


def test_evaluar_incompleto():
    datos = {"matricula": "1234ABC"}  # faltan dni_adquirente, dni_transmitente y cet
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is False
    assert "dni_adquirente" in faltantes
    assert "dni_transmitente" in faltantes


def test_evaluar_vacio():
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, {})
    assert completo is False
    assert set(faltantes) == {"matricula", "dni_adquirente", "dni_transmitente", "cet"}


def test_evaluar_tipo_sin_campos():
    """Tipos sin campos requeridos siempre completos."""
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.HOJA_CAJA, {})
    assert completo is True
    assert faltantes == []


def test_campo_none_cuenta_como_faltante():
    datos = {"matricula": "1234ABC", "dni_adquirente": None, "dni_transmitente": ""}
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is False
    assert "dni_adquirente" in faltantes
    assert "dni_transmitente" in faltantes
