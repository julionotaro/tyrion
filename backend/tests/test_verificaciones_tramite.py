"""Tests de verificaciones: datos de prueba + serialización del worker_email."""
import pytest
from app.api.datos_prueba import TRAMITES_PRUEBA


# ── Datos de prueba ────────────────────────────────────────────────────────────

def _tramite(tid):
    return next(t for t in TRAMITES_PRUEBA if t["id"] == tid)


def test_t002_tiene_verificaciones():
    t = _tramite("t-002")
    verifs = t.get("verificaciones", [])
    assert len(verifs) == 2
    campos = {v["campo"] for v in verifs}
    assert "matricula" in campos
    assert "cet" in campos
    assert all(v["ok"] for v in verifs)


def test_t002_verificacion_matricula_tiene_docs():
    t = _tramite("t-002")
    mat = next(v for v in t["verificaciones"] if v["campo"] == "matricula")
    assert mat["valor"] == "5678 DEF"
    assert "CTI" in mat["docs"]
    assert "Modelo 620" in mat["docs"]


def test_t005_verificacion_bastidor_presente():
    t = _tramite("t-005")
    verifs = t.get("verificaciones", [])
    bast = next((v for v in verifs if v["campo"] == "bastidor"), None)
    assert bast is not None
    assert bast["ok"] is True
    assert bast.get("presente") is True
    assert bast["valor"] == "VF1RFD00060123456"


def test_t006_verificaciones_como_t002():
    t = _tramite("t-006")
    verifs = t.get("verificaciones", [])
    campos = {v["campo"] for v in verifs}
    assert "matricula" in campos and "cet" in campos
    assert all(v["ok"] for v in verifs)
    mat = next(v for v in verifs if v["campo"] == "matricula")
    assert mat["valor"] == "7890 MNO"


def test_t007_verificaciones_matricula_correcta():
    t = _tramite("t-007")
    mat = next(v for v in t["verificaciones"] if v["campo"] == "matricula")
    assert mat["valor"] == "2345 PQR"
    assert mat["ok"] is True


def test_t008_verificacion_negativa():
    t = _tramite("t-008")
    verifs = t.get("verificaciones", [])
    neg = next(v for v in verifs if not v["ok"])
    assert neg["campo"] == "tipo_documento"
    vals_docs = [x["doc"] for x in neg["vals"]]
    assert "Documento recibido" in vals_docs
    assert "Tipo requerido" in vals_docs
    vals_vals = [x["val"] for x in neg["vals"]]
    assert "hoja_caja" in vals_vals
    assert "permiso_circulacion" in vals_vals
    assert "aviso" in neg and len(neg["aviso"]) > 10


# ── Serialización en worker_email ──────────────────────────────────────────────

def test_serializar_verificaciones_todos_validos():
    """Con checklist completo, todas las verificaciones son ok=True."""
    from unittest.mock import MagicMock
    from app.services.worker_email import _serializar_verificaciones
    from app.services.motor_cotejo import EstadoChecklist
    from app.services.catalogo_documental import TipoTramite

    checklist = EstadoChecklist(
        tipo_tramite=TipoTramite.TRANSFERENCIA,
        requisitos_validos=["cti", "modelo_620"],
        requisitos_faltantes=[],
        requisitos_evidencia=[],
        requisitos_rechazados=[],
    )
    verifs = _serializar_verificaciones(checklist, {})
    assert len(verifs) == 2
    assert all(v["ok"] for v in verifs)
    campos = {v["campo"] for v in verifs}
    assert campos == {"cti", "modelo_620"}


def test_serializar_verificaciones_rechazado():
    """Con un requisito rechazado, la verificación es ok=False con vals[]."""
    from app.services.worker_email import _serializar_verificaciones
    from app.services.motor_cotejo import EstadoChecklist
    from app.services.catalogo_documental import TipoTramite

    checklist = EstadoChecklist(
        tipo_tramite=TipoTramite.BAJA,
        requisitos_validos=["dni"],
        requisitos_faltantes=[],
        requisitos_evidencia=[],
        requisitos_rechazados=["solicitud_baja"],
    )
    verifs = _serializar_verificaciones(checklist, {})
    rech = next(v for v in verifs if v["campo"] == "solicitud_baja")
    assert rech["ok"] is False
    assert "vals" in rech
    assert "aviso" in rech


def test_serializar_verificaciones_faltante():
    """Con un requisito faltante, la verificación es ok=False."""
    from app.services.worker_email import _serializar_verificaciones
    from app.services.motor_cotejo import EstadoChecklist
    from app.services.catalogo_documental import TipoTramite

    checklist = EstadoChecklist(
        tipo_tramite=TipoTramite.TRANSFERENCIA,
        requisitos_validos=["cti"],
        requisitos_faltantes=["modelo_620"],
        requisitos_evidencia=[],
        requisitos_rechazados=[],
    )
    verifs = _serializar_verificaciones(checklist, {})
    falt = next(v for v in verifs if v["campo"] == "modelo_620")
    assert falt["ok"] is False


def test_serializar_verificaciones_sin_checklist():
    """Sin checklist devuelve lista vacía."""
    from app.services.worker_email import _serializar_verificaciones
    assert _serializar_verificaciones(None, {}) == []
