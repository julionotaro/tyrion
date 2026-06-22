"""Tests para motor_cruce: normalizadores, matching nombres y cotejar_datos."""
import pytest
from app.services.motor_cruce import (
    _coincide_nombre, _norm_documento_id, _norm_matricula,
    cotejar_datos, Criticidad,
)


def test_coincide_nombre_orden_invertido():
    assert _coincide_nombre("IVAN SOUTO PEREZ", "PEREZ IVAN SOUTO") is True

def test_coincide_nombre_abreviatura():
    assert _coincide_nombre("MARIA C. CARBALLAL LORES", "CARBALLAL LORES MARIA CARMEN") is True

def test_no_coincide_nombre():
    assert _coincide_nombre("IVAN SOUTO PEREZ", "PAULA FERNANDEZ COTO") is False

def test_norm_documento_id():
    assert _norm_documento_id("35.306.584-C") == "35306584C"
    assert _norm_documento_id("35 306 584 C") == "35306584C"

def test_norm_matricula():
    assert _norm_matricula("5042 HZM") == "5042HZM"
    assert _norm_matricula("5042-HZM") == "5042HZM"


# ── cotejar_datos: transferencia simple ───────────────────────────────────────

def _docs_transferencia(
    dni_adq_cti="35306584C", dni_adq_620="35306584C",
    dni_tra_cti="14958073T", dni_tra_620="14958073T",
    mat_cti="5042HZM", mat_620="5042HZM",
):
    return {
        "cti": {
            "matricula": mat_cti,
            "dni_adquirente": dni_adq_cti,
            "dni_transmitente": dni_tra_cti,
            "nombre_adquirente": "MARIA CARBALLAL LORES",
            "nombre_transmitente": "JOSE GONZALEZ FERNANDEZ",
            "cet": "NO",
        },
        "modelo_620": {
            "matricula": mat_620,
            "nif_adquirente": dni_adq_620,
            "nif_transmitente": dni_tra_620,
            "nombre_adquirente": "CARBALLAL LORES MARIA",
            "nombre_transmitente": "GONZALEZ FERNANDEZ JOSE",
            "cet": "NO",
        },
    }


def test_transferencia_dnis_coinciden_ok():
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", _docs_transferencia())
    criticas = [v for v in verifs if v["criticidad"] == "CRITICA"]
    assert all(v["ok"] or v["estado"] == "incompleto" for v in criticas)


def test_transferencia_dni_adquirente_discrepante():
    docs = _docs_transferencia(dni_adq_620="53111223H")
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", docs)
    cruce = next(v for v in verifs if "dni_adquirente" in v["campo"])
    assert cruce["estado"] == "discrepancia"
    assert cruce["criticidad"] == "CRITICA"
    assert cruce["ok"] is False
    assert "aviso" in cruce


def test_transferencia_nombres_invertidos_no_son_criticos():
    """Nombres en orden invertido → ADVERTENCIA, no bloquea."""
    docs = _docs_transferencia()
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", docs)
    nombre_verifs = [v for v in verifs if "nombre" in v["campo"]]
    # Con matching tolerante deben ser ok o advertencia, nunca CRITICA con discrepancia
    for v in nombre_verifs:
        if v["estado"] == "discrepancia":
            assert v["criticidad"] == "ADVERTENCIA"


def test_campo_ausente_en_un_doc_incompleto():
    """Si un campo está presente solo en un lado → estado=incompleto."""
    docs = {
        "cti": {"matricula": "5042HZM", "dni_adquirente": "35306584C", "dni_transmitente": "14958073T"},
        "modelo_620": {"matricula": "5042HZM", "nif_adquirente": None, "nif_transmitente": "14958073T"},
    }
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", docs)
    cruce_adq = next(v for v in verifs if "dni_adquirente" in v["campo"])
    assert cruce_adq["estado"] == "incompleto"
    assert cruce_adq["ok"] is False


def test_sin_modelo_620_no_hay_cruces():
    docs = {"cti": {"matricula": "5042HZM", "dni_adquirente": "35306584C"}}
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", docs)
    assert verifs == []


# ── cotejar_datos: herencia ───────────────────────────────────────────────────

def test_herencia_matricula_discrepante():
    docs = {
        "declaracion_responsable_fallecimiento": {"matricula": "5042HZM", "dni": "35306584C", "nombre": "MARIA GARCIA"},
        "anexo_650": {"matricula": "9999ZZZ", "bastidor": "WBA1", "valor_vehiculo": "12000"},
        "modelo_650": {"dni_causante": "11111111A", "dni_sujeto_pasivo": "35306584C", "importe": "100"},
    }
    verifs = cotejar_datos("TRANSFERENCIA", "herencia", docs)
    mat_cruce = next(v for v in verifs if "matricula" in v["campo"] and "anexo_650" in v["campo"])
    assert mat_cruce["estado"] == "discrepancia"
    assert mat_cruce["criticidad"] == "CRITICA"


def test_herencia_sin_certificado_defuncion_omite_reglas_causante():
    """Sin certificado_defuncion → reglas que lo involucran se omiten."""
    docs = {
        "declaracion_responsable_fallecimiento": {"matricula": "5042HZM", "dni": "35306584C", "nombre": "MARIA"},
        "anexo_650": {"matricula": "5042HZM", "bastidor": "WBA1", "valor_vehiculo": "12000"},
        "modelo_650": {"dni_causante": "11111111A", "dni_sujeto_pasivo": "35306584C", "importe": "100"},
    }
    verifs = cotejar_datos("TRANSFERENCIA", "herencia", docs)
    campos = [v["campo"] for v in verifs]
    # No debe haber cruces con certificado_defuncion
    assert not any("certificado_defuncion" in c for c in campos)
