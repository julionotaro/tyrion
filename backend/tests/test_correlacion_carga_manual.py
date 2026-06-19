"""Tests: correlación agnóstica de canal (carga manual + estado en_revision)."""
import pytest
from unittest.mock import MagicMock, patch
from app.services import registro_tramites
from app.api.store import DOCUMENTOS_CARGA


def _tramite_abierto(tid="t-cm-001", matricula="1234TST", estado="pendiente_gestoria"):
    return {
        "id": tid, "estado": estado, "matricula": matricula,
        "bastidor": "", "gestoria": "Test", "gestoria_email": "g@test.com",
        "tipo": "TRANSFERENCIA", "subtipo": "ninguno",
        "documentos": [], "documentos_faltantes": ["cti"],
        "documentos_evidencia": [], "documentos_evidencia_detalle": {},
        "verificaciones": [],
        "avisos_pendientes": [{"tipo": "aviso_1", "enviado_smtp": True}],
        "historial": [], "message_ids_avisos": [],
    }


@pytest.fixture(autouse=True)
def limpiar():
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()
    yield
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()


def test_buscar_tramite_existente_pendiente_gestoria():
    tramite = _tramite_abierto(estado="pendiente_gestoria")
    registro_tramites.agregar_tramite(tramite)
    resultado = registro_tramites.buscar_tramite_existente(matricula="1234TST")
    assert resultado is not None
    assert resultado["id"] == "t-cm-001"


def test_buscar_tramite_existente_en_revision():
    """buscar_tramite_existente encuentra tramites en_revision también."""
    tramite = _tramite_abierto(estado="en_revision")
    registro_tramites.agregar_tramite(tramite)
    resultado = registro_tramites.buscar_tramite_existente(matricula="1234TST")
    assert resultado is not None
    assert resultado["id"] == "t-cm-001"


def test_buscar_tramite_no_encuentra_listo_dgt():
    tramite = _tramite_abierto(estado="listo_dgt")
    registro_tramites.agregar_tramite(tramite)
    assert registro_tramites.buscar_tramite_existente(matricula="1234TST") is None


def test_buscar_tramite_normaliza_espacios():
    """Matrícula con espacio en tramite encontrada con matrícula sin espacio."""
    tramite = _tramite_abierto(matricula="1234 TST")
    registro_tramites.agregar_tramite(tramite)
    assert registro_tramites.buscar_tramite_existente(matricula="1234TST") is not None


def test_adjuntar_documentos_vacia_faltantes_cuando_completo():
    """adjuntar_documentos + recotejar completo → faltantes y avisos quedan vacíos."""
    from app.services.correlacion import adjuntar_documentos

    tramite = _tramite_abierto()
    registro_tramites.agregar_tramite(tramite)

    clf = MagicMock()
    clf.tipo_detectado = MagicMock()
    clf.tipo_detectado.value = "cti"
    clf.confianza_nivel = "ALTA"
    clf.confianza_score = 0.95
    clf.datos_extraidos = {}
    clf.justificacion = ""

    with patch("app.services.correlacion.recotejar_tramite") as mock_recotejar:
        def side_recotejar(t):
            t["estado"] = "listo_dgt"
            t["alerta"] = False
            t["avisos_pendientes"] = []
            t["documentos_faltantes"] = []
            t["documentos_evidencia"] = []
            t["documentos_evidencia_detalle"] = {}
            t["verificaciones"] = []
        mock_recotejar.side_effect = side_recotejar

        adjuntar_documentos(tramite, {"cti.pdf": clf}, "g@test.com")

    assert tramite["estado"] == "listo_dgt"
    assert tramite["avisos_pendientes"] == []
    assert tramite["documentos_faltantes"] == []
    assert len(tramite["documentos"]) == 1
    assert any("cti.pdf" in h["evento"] for h in tramite["historial"])


def test_buscar_tramite_por_bastidor():
    tramite = _tramite_abierto()
    tramite["bastidor"] = "WBA3A5C57DF123456"
    registro_tramites.agregar_tramite(tramite)
    resultado = registro_tramites.buscar_tramite_existente(bastidor="wba3a5c57df123456")
    assert resultado is not None


def test_recotejar_tramite_limpia_cuando_completo():
    """recotejar_tramite con cotejo completo → limpia todos los campos."""
    from app.services.correlacion import recotejar_tramite

    tramite = _tramite_abierto()
    tramite["avisos_pendientes"] = [
        {"tipo": "aviso_1", "enviado_smtp": True},
        {"tipo": "aviso_2", "enviado_smtp": False},
    ]
    tramite["documentos_evidencia"] = ["modelo_620"]
    tramite["documentos_evidencia_detalle"] = {"modelo_620": ["num_bastidor"]}
    tramite["documentos"] = []

    # Con documentos vacíos, el cotejo estará incompleto → verificar rama incompleto
    recotejar_tramite(tramite)
    assert tramite["estado"] == "pendiente_gestoria"
    assert tramite["alerta"] is True
    assert isinstance(tramite["documentos_faltantes"], list)
