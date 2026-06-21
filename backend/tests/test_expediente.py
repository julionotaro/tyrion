"""Tests para el modelo de expediente: correlación robusta por identificador."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services import registro_tramites
from app.api.store import DOCUMENTOS_CARGA


def _tramite(tid="t-exp-001", matricula="5042HZM", bastidor="", estado="pendiente_gestoria"):
    return {
        "id": tid, "estado": estado, "matricula": matricula, "bastidor": bastidor,
        "gestoria": "Test", "gestoria_email": "g@test.com",
        "tipo": "TRANSFERENCIA", "subtipo": "ninguno",
        "documentos": [], "documentos_faltantes": ["cti"],
        "documentos_evidencia": [], "documentos_evidencia_detalle": {},
        "verificaciones": [], "avisos_pendientes": [], "historial": [],
        "message_ids_avisos": [],
    }


def _clf_mock(tipo="cti", matricula="5042HZM", bastidor=""):
    clf = MagicMock()
    clf.tipo_detectado = MagicMock()
    clf.tipo_detectado.value = tipo
    clf.confianza_nivel = "ALTA"
    clf.confianza_score = 0.95
    clf.datos_extraidos = {"matricula": matricula} if matricula else ({"bastidor": bastidor} if bastidor else {})
    clf.justificacion = ""
    return clf


@pytest.fixture(autouse=True)
def limpiar():
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()
    yield
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()


def test_dos_llegadas_misma_matricula_un_expediente():
    """Email + carga manual con misma matrícula → solo un expediente, doc adjuntado."""
    t = _tramite()
    registro_tramites.agregar_tramite(t)

    # Segunda llegada con misma matrícula
    resultado = registro_tramites.buscar_expediente(matricula="5042HZM")
    assert resultado is not None
    assert resultado["id"] == "t-exp-001"


def test_listo_dgt_sigue_correlacionando():
    """Un expediente en listo_dgt aún correlaciona con nuevo doc (no es cerrado)."""
    t = _tramite(estado="listo_dgt")
    registro_tramites.agregar_tramite(t)

    resultado = registro_tramites.buscar_expediente(matricula="5042HZM")
    assert resultado is not None
    assert resultado["id"] == "t-exp-001"


def test_cerrado_no_correlaciona():
    """Un expediente cerrado no correlaciona."""
    t = _tramite(estado="cerrado")
    registro_tramites.agregar_tramite(t)

    resultado = registro_tramites.buscar_expediente(matricula="5042HZM")
    assert resultado is None


def test_bastidor_despues_correlaciona_con_matricula():
    """Tramite creado con matrícula; nuevo doc trae bastidor → correlaciona y acumula."""
    t = _tramite(matricula="5042HZM")
    registro_tramites.agregar_tramite(t)

    # Buscar por bastidor (no había bastidor en el trámite originalmente)
    # Primero, acumular bastidor
    registro_tramites.actualizar_identificadores(t, None, "WBA3A5C57DF123456")

    resultado = registro_tramites.buscar_expediente(bastidor="WBA3A5C57DF123456")
    assert resultado is not None
    assert resultado["id"] == "t-exp-001"
    assert resultado["identificadores"].get("bastidor") == "WBA3A5C57DF123456"
    assert resultado["identificadores"].get("matricula") == "5042HZM"


def test_actualizar_identificadores_no_sobreescribe():
    """actualizar_identificadores no reemplaza un identificador ya existente."""
    t = _tramite(matricula="5042HZM")
    registro_tramites.agregar_tramite(t)

    registro_tramites.actualizar_identificadores(t, "OTRO-MAT", "WBA3A5C57DF123456")

    ids = t["identificadores"]
    assert ids["matricula"] == "5042HZM"   # no se sobreescribió
    assert ids["bastidor"] == "WBA3A5C57DF123456"  # se acumuló


@pytest.mark.asyncio
async def test_ingestar_documentos_correlaciona_existente():
    """ingestar_documentos adjunta a trámite existente (es_nuevo=False)."""
    from app.services.correlacion import ingestar_documentos

    t = _tramite()
    registro_tramites.agregar_tramite(t)

    clf = _clf_mock(matricula="5042HZM")
    clasificaciones = {"doc.pdf": clf}

    crear_fn = MagicMock(return_value={})
    with patch("app.services.correlacion.adjuntar_documentos") as mock_adj:
        tramite_ret, es_nuevo = await ingestar_documentos(
            clasificaciones=clasificaciones,
            crear_tramite_fn=crear_fn,
            matricula_declarada="5042HZM",
        )

    assert es_nuevo is False
    assert tramite_ret["id"] == "t-exp-001"
    mock_adj.assert_called_once()
    crear_fn.assert_not_called()


@pytest.mark.asyncio
async def test_ingestar_documentos_crea_nuevo():
    """ingestar_documentos crea nuevo trámite si no hay correlación (es_nuevo=True)."""
    from app.services.correlacion import ingestar_documentos

    nuevo_tramite = _tramite(tid="t-nuevo", matricula="9999ZZZ")
    crear_fn = MagicMock(return_value=nuevo_tramite)

    clf = _clf_mock(tipo="cti", matricula="9999ZZZ")
    clasificaciones = {"doc.pdf": clf}

    tramite_ret, es_nuevo = await ingestar_documentos(
        clasificaciones=clasificaciones,
        crear_tramite_fn=crear_fn,
        matricula_declarada="9999ZZZ",
    )

    assert es_nuevo is True
    crear_fn.assert_called_once()
    assert registro_tramites.obtener_tramite("t-nuevo") is not None


@pytest.mark.asyncio
async def test_ingestar_documentos_sin_identificador_marca_sin_correlacionar():
    """ingestar_documentos sin mat/bas → estado sin_correlacionar."""
    from app.services.correlacion import ingestar_documentos

    tramite_base = {
        "id": "t-sc-001", "estado": "pendiente_gestoria",
        "matricula": None, "bastidor": None,
        "gestoria": "Test", "gestoria_email": "g@test.com",
        "tipo": "SIN_DETERMINAR", "subtipo": "ninguno",
        "documentos": [], "documentos_faltantes": [],
        "documentos_evidencia": [], "documentos_evidencia_detalle": {},
        "verificaciones": [], "avisos_pendientes": [], "historial": [],
        "message_ids_avisos": [],
    }
    crear_fn = MagicMock(return_value=tramite_base)

    clf = MagicMock()
    clf.tipo_detectado = MagicMock()
    clf.tipo_detectado.value = "desconocido"
    clf.confianza_nivel = "BAJA"
    clf.confianza_score = 0.3
    clf.datos_extraidos = {}
    clf.justificacion = ""
    clasificaciones = {"doc.pdf": clf}

    tramite_ret, es_nuevo = await ingestar_documentos(
        clasificaciones=clasificaciones,
        crear_tramite_fn=crear_fn,
    )

    assert es_nuevo is True
    assert tramite_ret["estado"] == "sin_correlacionar"
    assert tramite_ret["alerta"] is True
