"""Tests: completo con discrepancia CRITICA → no completo; con solo ADVERTENCIA → sí completo."""
from app.services.motor_cotejo import EstadoChecklist
from app.services.catalogo_documental import TipoTramite


def _estado(verifs):
    e = EstadoChecklist(tipo_tramite=TipoTramite.TRANSFERENCIA)
    e.verificaciones = verifs
    return e


def test_discrepancia_critica_bloquea_completo():
    e = _estado([{"estado": "discrepancia", "criticidad": "CRITICA", "ok": False}])
    assert e.completo is False
    assert e.debe_pedir_gestoria is True
    assert len(e.verificaciones_fallidas) == 1


def test_advertencia_no_bloquea_completo():
    e = _estado([{"estado": "discrepancia", "criticidad": "ADVERTENCIA", "ok": False}])
    assert e.completo is True
    assert e.verificaciones_fallidas == []


def test_incompleto_no_bloquea_completo():
    e = _estado([{"estado": "incompleto", "criticidad": "CRITICA", "ok": False}])
    assert e.completo is True
    assert e.verificaciones_fallidas == []


def test_sin_verificaciones_completo_segun_requisitos():
    e = _estado([])
    assert e.completo is True
