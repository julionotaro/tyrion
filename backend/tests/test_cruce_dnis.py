"""Tests de cruce de identidad — migrado a motor_cruce.cotejar_datos."""
from app.services.motor_cruce import cotejar_datos


def _docs(dni_adq_cti, dni_adq_620, dni_tra_cti="14958073T", dni_tra_620="14958073T"):
    return {
        "cti": {"matricula": "5042HZM", "dni_adquirente": dni_adq_cti, "dni_transmitente": dni_tra_cti},
        "modelo_620": {"matricula": "5042HZM", "nif_adquirente": dni_adq_620, "nif_transmitente": dni_tra_620},
    }


def test_dnis_coinciden_ok_true():
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", _docs("35306584C", "35306584C"))
    cruce = next(v for v in verifs if "dni_adquirente" in v["campo"])
    assert cruce["ok"] is True
    assert cruce["estado"] == "ok"


def test_dnis_discrepantes_ok_false():
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", _docs("35306584C", "99999999Z"))
    cruce = next(v for v in verifs if "dni_adquirente" in v["campo"])
    assert cruce["ok"] is False
    assert cruce["estado"] == "discrepancia"
    assert "aviso" in cruce
    assert "35306584C" in cruce["aviso"]
    assert "99999999Z" in cruce["aviso"]


def test_sin_modelo_620_no_hay_cruces():
    docs = {"cti": {"matricula": "5042HZM", "dni_adquirente": "35306584C"}}
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno", docs)
    assert verifs == []


def test_normaliza_espacios_y_guiones():
    verifs = cotejar_datos("TRANSFERENCIA", "ninguno",
        _docs("35306584-C", "35306584C", "14 958073T", "14958073T"))
    assert all(v["ok"] for v in verifs if "dni" in v["campo"])
