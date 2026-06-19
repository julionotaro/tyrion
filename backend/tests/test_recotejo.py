"""Tests para re-cotejo sobre trámite existente al recibir respuesta email."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass, field

from app.api.store import DOCUMENTOS_CARGA
from app.services import registro_tramites


@dataclass
class _Adjunto:
    nombre: str
    content_type: str
    contenido: bytes


@dataclass
class _Email:
    message_id: str = "<resp@test.com>"
    remitente: str = "gestoria@test.com"
    asunto: str = ""
    fecha: str = ""
    in_reply_to: str = "<aviso1@tyrion.colegio>"
    references: str = ""
    adjuntos: list = field(default_factory=list)

    @property
    def tiene_adjuntos_utiles(self):
        return bool(self.adjuntos)


def _tramite_pendiente(tid="t-rc-001", faltantes=None):
    return {
        "id": tid,
        "estado": "pendiente_gestoria",
        "matricula": "1234TST",
        "bastidor": "",
        "gestoria": "Gestoría Test",
        "gestoria_email": "gestoria@test.com",
        "tipo": "TRANSFERENCIA",
        "subtipo": "ninguno",
        "documentos": [],
        "documentos_faltantes": faltantes or ["cti"],
        "documentos_evidencia": [],
        "verificaciones": [],
        "avisos_pendientes": [{"tipo": "aviso_1", "enviado_smtp": True}],
        "historial": [],
        "message_ids_avisos": ["<aviso1@tyrion.colegio>"],
        "alerta": True,
    }


def _resultado_checklist_completo():
    m = MagicMock()
    m.completo = True
    m.debe_escalar_admin = False
    m.requisitos_faltantes = []
    m.requisitos_evidencia = []
    return m


def _resultado_checklist_incompleto(faltantes=None):
    m = MagicMock()
    m.completo = False
    m.debe_escalar_admin = False
    m.requisitos_faltantes = faltantes or ["cti"]
    m.requisitos_evidencia = []
    return m


@pytest.fixture(autouse=True)
def limpiar():
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()
    yield
    registro_tramites.reset()
    DOCUMENTOS_CARGA.clear()


@pytest.mark.asyncio
async def test_adjuntar_completa_tramite():
    """Documento que faltaba llega → cotejo completo → estado listo_dgt."""
    from app.schemas.clasificacion import ResultadoClasificacion
    from app.services.catalogo_documental import TipoDocumento
    from app.services.worker_email import adjuntar_a_tramite

    tramite = _tramite_pendiente()
    clf_cti = MagicMock(spec=ResultadoClasificacion)
    clf_cti.tipo_detectado = TipoDocumento.CTI
    clf_cti.confianza_nivel = "ALTA"
    clf_cti.confianza_score = 0.95
    clf_cti.datos_extraidos = {}
    clf_cti.justificacion = ""

    email = _Email(
        adjuntos=[_Adjunto(nombre="cti.pdf", content_type="application/pdf", contenido=b"PDF")]
    )
    clasificaciones = {"cti.pdf": clf_cti}

    checklist_ok = _resultado_checklist_completo()

    with patch("app.services.worker_email._recotejar_tramite") as mock_recotejar, \
         patch("app.services.worker_email.guardar_archivo"):
        def side_recotejar(t):
            t["estado"] = "listo_dgt"
            t["alerta"] = False
            t["documentos_faltantes"] = []
            t["documentos_evidencia"] = []
            t["verificaciones"] = []
        mock_recotejar.side_effect = side_recotejar

        await adjuntar_a_tramite(tramite, email, clasificaciones)

    assert tramite["estado"] == "listo_dgt"
    assert tramite["alerta"] is False
    assert len(tramite["documentos"]) == 1
    assert any("Cotejo actualizado → listo_dgt" in h["evento"] for h in tramite["historial"])


@pytest.mark.asyncio
async def test_adjuntar_incompleto_permanece_pendiente():
    """Si aún faltan docs tras adjuntar, estado permanece pendiente_gestoria."""
    from app.schemas.clasificacion import ResultadoClasificacion
    from app.services.catalogo_documental import TipoDocumento
    from app.services.worker_email import adjuntar_a_tramite

    tramite = _tramite_pendiente(faltantes=["cti", "modelo_620"])
    clf = MagicMock(spec=ResultadoClasificacion)
    clf.tipo_detectado = TipoDocumento.CTI
    clf.confianza_nivel = "ALTA"
    clf.confianza_score = 0.9
    clf.datos_extraidos = {}
    clf.justificacion = ""

    email = _Email(adjuntos=[_Adjunto("cti.pdf", "application/pdf", b"PDF")])
    clasificaciones = {"cti.pdf": clf}

    with patch("app.services.worker_email._recotejar_tramite") as mock_recotejar, \
         patch("app.services.worker_email.guardar_archivo"):
        def side_recotejar(t):
            t["estado"] = "pendiente_gestoria"
            t["alerta"] = True
            t["documentos_faltantes"] = ["modelo_620"]
            t["documentos_evidencia"] = []
            t["verificaciones"] = []
        mock_recotejar.side_effect = side_recotejar

        await adjuntar_a_tramite(tramite, email, clasificaciones)

    assert tramite["estado"] == "pendiente_gestoria"
    assert len(tramite["historial"]) == 1


@pytest.mark.asyncio
async def test_historial_incluye_nombre_documento():
    """El historial registra el nombre del documento adjuntado."""
    from app.schemas.clasificacion import ResultadoClasificacion
    from app.services.catalogo_documental import TipoDocumento
    from app.services.worker_email import adjuntar_a_tramite

    tramite = _tramite_pendiente()
    clf = MagicMock(spec=ResultadoClasificacion)
    clf.tipo_detectado = TipoDocumento.CTI
    clf.confianza_nivel = "ALTA"
    clf.confianza_score = 0.9
    clf.datos_extraidos = {}
    clf.justificacion = ""

    email = _Email(remitente="mis@gestoria.com", adjuntos=[_Adjunto("permiso.pdf", "application/pdf", b"")])
    clasificaciones = {"permiso.pdf": clf}

    with patch("app.services.worker_email._recotejar_tramite") as mock_recotejar, \
         patch("app.services.worker_email.guardar_archivo"):
        mock_recotejar.side_effect = lambda t: t.update({"estado": "pendiente_gestoria", "alerta": True, "documentos_faltantes": [], "documentos_evidencia": [], "verificaciones": []})
        await adjuntar_a_tramite(tramite, email, clasificaciones)

    evento = tramite["historial"][0]["evento"]
    assert "mis@gestoria.com" in evento
    assert "permiso.pdf" in evento
