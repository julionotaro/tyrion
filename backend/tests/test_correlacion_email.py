"""Tests para correlación de respuestas email con trámites existentes."""
import pytest
from dataclasses import dataclass, field
from app.services import registro_tramites


@dataclass
class _Email:
    message_id: str = "<new@test.com>"
    remitente: str = "gestoria@test.com"
    asunto: str = ""
    fecha: str = ""
    in_reply_to: str = ""
    references: str = ""
    adjuntos: list = field(default_factory=list)


def _tramite_base(tid="t-001", matricula="1234TST", bastidor="", estado="pendiente_gestoria", avisos_mid=None):
    return {
        "id": tid,
        "estado": estado,
        "matricula": matricula,
        "bastidor": bastidor,
        "gestoria": "Test",
        "gestoria_email": "gestoria@test.com",
        "tipo": "TRANSFERENCIA",
        "message_ids_avisos": avisos_mid or [],
        "avisos_pendientes": [],
        "historial": [],
    }


@pytest.fixture(autouse=True)
def limpiar():
    registro_tramites.reset()
    yield
    registro_tramites.reset()


def test_correlacion_por_in_reply_to():
    """Email con In-Reply-To apuntando a un aviso enviado → tramite encontrado."""
    tramite = _tramite_base(avisos_mid=["<aviso1@tyrion.colegio>"])
    registro_tramites.agregar_tramite(tramite)

    email = _Email(in_reply_to="<aviso1@tyrion.colegio>")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is not None
    assert resultado["id"] == "t-001"


def test_correlacion_por_references():
    """Email con References apuntando a un aviso → tramite encontrado."""
    tramite = _tramite_base(avisos_mid=["<aviso2@tyrion.colegio>"])
    registro_tramites.agregar_tramite(tramite)

    email = _Email(references="<otro@x.com> <aviso2@tyrion.colegio>")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is not None
    assert resultado["id"] == "t-001"


def test_correlacion_por_matricula_en_asunto():
    """Email sin In-Reply-To pero con matrícula en asunto → tramite encontrado."""
    tramite = _tramite_base(matricula="5678 ABC")
    registro_tramites.agregar_tramite(tramite)

    email = _Email(asunto="Re: Trámite matrícula 5678ABC - documentación")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is not None
    assert resultado["id"] == "t-001"


def test_correlacion_por_matricula_con_espacio():
    """Matrícula con espacio en asunto normalizada correctamente."""
    tramite = _tramite_base(matricula="5678ABC")
    registro_tramites.agregar_tramite(tramite)

    email = _Email(asunto="Documentos 5678 ABC pendientes")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is not None


def test_correlacion_por_bastidor_en_asunto():
    """Email con bastidor VIN en asunto → tramite encontrado."""
    tramite = _tramite_base(bastidor="WBA3A5C57DF123456")
    registro_tramites.agregar_tramite(tramite)

    email = _Email(asunto="Expediente WBA3A5C57DF123456 — adjunto documentación")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is not None
    assert resultado["id"] == "t-001"


def test_sin_correlacion_retorna_none():
    """Email que no correlaciona con ningún trámite → None."""
    tramite = _tramite_base(matricula="9999ZZZ")
    registro_tramites.agregar_tramite(tramite)

    email = _Email(asunto="Sin matrícula ni referencia conocida")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is None


def test_correlacion_por_matricula_solo_estado_pendiente():
    """La búsqueda por matrícula solo aplica a trámites en pendiente_gestoria."""
    tramite = _tramite_base(matricula="1234TST", estado="listo_dgt")
    registro_tramites.agregar_tramite(tramite)

    email = _Email(asunto="Docs matrícula 1234 TST")
    resultado = registro_tramites.buscar_tramite_para_respuesta(email)
    assert resultado is None
