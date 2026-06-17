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
    assert campos_requeridos(TipoDocumento.CTI) == ["matricula", "titular", "bastidor"]
    assert campos_requeridos(TipoDocumento.DESCONOCIDO) == []


def test_evaluar_completo():
    datos = {"matricula": "1234ABC", "titular": "Juan García", "bastidor": "WBA12345"}
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is True
    assert faltantes == []


def test_evaluar_incompleto():
    datos = {"matricula": "1234ABC"}  # faltan titular y bastidor
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is False
    assert "titular" in faltantes
    assert "bastidor" in faltantes


def test_evaluar_vacio():
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, {})
    assert completo is False
    assert set(faltantes) == {"matricula", "titular", "bastidor"}


def test_evaluar_tipo_sin_campos():
    """Tipos sin campos requeridos siempre completos."""
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.HOJA_CAJA, {})
    assert completo is True
    assert faltantes == []


def test_campo_none_cuenta_como_faltante():
    datos = {"matricula": "1234ABC", "titular": None, "bastidor": ""}
    completo, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos)
    assert completo is False
    assert "titular" in faltantes
    assert "bastidor" in faltantes
