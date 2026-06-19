"""Tests para correlacion.extraer_identificador."""
import pytest
from unittest.mock import MagicMock
from app.services.correlacion import extraer_identificador


def _clf(matricula=None, bastidor=None, num_bastidor=None):
    m = MagicMock()
    m.datos_extraidos = {}
    if matricula:
        m.datos_extraidos["matricula"] = matricula
    if bastidor:
        m.datos_extraidos["bastidor"] = bastidor
    if num_bastidor:
        m.datos_extraidos["num_bastidor"] = num_bastidor
    return m


def test_transferencia_extrae_matricula():
    clfs = {"cti.pdf": _clf(matricula="1234 TST")}
    mat, bas = extraer_identificador("TRANSFERENCIA", clfs)
    assert mat == "1234TST"
    assert bas is None


def test_normaliza_espacios_y_guiones():
    clfs = {"cti.pdf": _clf(matricula="56-78 ABC")}
    mat, _ = extraer_identificador("TRANSFERENCIA", clfs)
    assert mat == "5678ABC"


def test_matriculacion_extrae_bastidor():
    clfs = {"ficha.pdf": _clf(bastidor="WBA3A5C57DF123456")}
    mat, bas = extraer_identificador("MATRICULACION", clfs)
    assert bas == "WBA3A5C57DF123456"


def test_busca_en_todos_los_docs():
    clfs = {
        "doc1.pdf": _clf(),
        "doc2.pdf": _clf(matricula="5678ABC", bastidor="WBA3A5C57DF123456"),
    }
    mat, bas = extraer_identificador("TRANSFERENCIA", clfs)
    assert mat == "5678ABC"
    assert bas == "WBA3A5C57DF123456"


def test_num_bastidor_alternativo():
    clfs = {"ficha.pdf": _clf(num_bastidor="XYZ99999XXXXXXXXX")}
    _, bas = extraer_identificador("TRANSFERENCIA", clfs)
    assert bas == "XYZ99999XXXXXXXXX"


def test_acepta_dict_con_campos_extraidos():
    """Acepta dicts con campos_extraidos (formato DOCUMENTOS_CARGA)."""
    doc = {"campos_extraidos": [{"campo": "matricula", "valor": "9999ZZZ"}]}
    mat, bas = extraer_identificador("TRANSFERENCIA", {"doc.pdf": doc})
    assert mat == "9999ZZZ"
    assert bas is None


def test_sin_datos_retorna_none_none():
    clfs = {"doc.pdf": _clf()}
    mat, bas = extraer_identificador("TRANSFERENCIA", clfs)
    assert mat is None
    assert bas is None
