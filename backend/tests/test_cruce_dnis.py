"""Tests para verificar_identidad_transferencia: cruce DNI entre CTI y modelo_620."""
from unittest.mock import MagicMock
from app.services.motor_cotejo import verificar_identidad_transferencia
from app.services.catalogo_documental import TipoDocumento


def _clf(tipo: str, datos: dict):
    m = MagicMock()
    m.tipo_detectado = MagicMock()
    m.tipo_detectado.value = tipo
    m.datos_extraidos = datos
    return m


def test_dnis_coinciden_ok_true():
    """CTI y modelo_620 con mismos DNIs → verificación ok=True."""
    clfs = {
        "cti.pdf": _clf("cti", {
            "matricula": "5042HZM",
            "dni_adquirente": "35306584C",
            "dni_transmitente": "14958073T",
            "cet": "CET-001",
        }),
        "620.pdf": _clf("modelo_620", {
            "matricula": "5042HZM",
            "nif_adquirente": "35306584C",
            "nif_transmitente": "14958073T",
            "cet": "CET-001",
        }),
    }
    verifs = verificar_identidad_transferencia(clfs)
    assert len(verifs) == 2
    assert all(v["ok"] for v in verifs)
    campos = {v["campo"] for v in verifs}
    assert "cruce_dni_adquirente" in campos
    assert "cruce_dni_transmitente" in campos


def test_dnis_discrepantes_ok_false():
    """DNI adquirente distinto entre CTI y modelo_620 → ok=False con aviso."""
    clfs = {
        "cti.pdf": _clf("cti", {
            "matricula": "5042HZM",
            "dni_adquirente": "35306584C",
            "dni_transmitente": "14958073T",
            "cet": "NO",
        }),
        "620.pdf": _clf("modelo_620", {
            "matricula": "5042HZM",
            "nif_adquirente": "99999999Z",
            "nif_transmitente": "14958073T",
            "cet": "NO",
        }),
    }
    verifs = verificar_identidad_transferencia(clfs)
    cruce_adq = next(v for v in verifs if v["campo"] == "cruce_dni_adquirente")
    cruce_tra = next(v for v in verifs if v["campo"] == "cruce_dni_transmitente")

    assert cruce_adq["ok"] is False
    assert "aviso" in cruce_adq
    assert "35306584C" in cruce_adq["aviso"]
    assert "99999999Z" in cruce_adq["aviso"]

    assert cruce_tra["ok"] is True


def test_sin_modelo_620_no_hay_cruces():
    """Sin modelo_620 en clasificaciones → no se generan cruces."""
    clfs = {
        "cti.pdf": _clf("cti", {
            "matricula": "5042HZM",
            "dni_adquirente": "35306584C",
            "cet": "NO",
        }),
    }
    verifs = verificar_identidad_transferencia(clfs)
    assert verifs == []


def test_normaliza_espacios_y_guiones():
    """DNI con espacios o guiones normaliza correctamente."""
    clfs = {
        "cti.pdf": _clf("cti", {"dni_adquirente": "35306584-C", "dni_transmitente": "14958073T"}),
        "620.pdf": _clf("modelo_620", {"nif_adquirente": "35306584C", "nif_transmitente": "14 958073T"}),
    }
    verifs = verificar_identidad_transferencia(clfs)
    assert all(v["ok"] for v in verifs)
