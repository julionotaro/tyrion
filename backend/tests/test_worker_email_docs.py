"""
Tests: documentos de email registrados en DOCUMENTOS_CARGA y accesibles via API.

Verifica:
  - Cada documento del email tiene id no nulo (formato {tramite_id}-doc-{i})
  - Los documentos quedan registrados en DOCUMENTOS_CARGA
  - /api/documentos/{id}/extraccion los sirve (tiene_extraccion=True)
  - matricula y bastidor se extraen de los campos clasificados cuando están presentes
  - Sin campos de matrícula/bastidor → ambos quedan None
"""
import asyncio
import email as email_lib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.store import DOCUMENTOS_CARGA, reset as reset_store
from app.services import registro_tramites
from app.services.catalogo_documental import TipoDocumento
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services.worker_email import (
    _construir_tramite_email,
    _extraer_matricula_bastidor,
    run_email_worker,
)
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.ingesta_email import EmailEntrante, AdjuntoEmail


client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_raw(
    message_id: str,
    remitente: str = "gestoria@example.com",
    asunto: str = "Transferencia González",
    adjuntos: list[tuple[str, bytes]] | None = None,
) -> bytes:
    msg = MIMEMultipart()
    msg["Message-ID"] = message_id
    msg["From"] = remitente
    msg["Subject"] = asunto
    msg["Date"] = "Tue, 18 Jun 2026 09:00:00 +0000"
    msg.attach(MIMEText("Adjunto documentación.", "plain"))
    for nombre, contenido in (adjuntos or []):
        parte = MIMEApplication(contenido, Name=nombre)
        parte["Content-Disposition"] = f'attachment; filename="{nombre}"'
        msg.attach(parte)
    return msg.as_bytes()


class FuenteEnMemoria:
    def __init__(self, crudos: list[bytes]):
        self._crudos = crudos

    def mensajes_crudos(self) -> list[bytes]:
        return self._crudos


class ClasificadorMock:
    """Devuelve CTI con matrícula y bastidor en datos_extraidos."""
    def __init__(self, tipo: TipoDocumento = TipoDocumento.CTI, datos: dict | None = None):
        self._tipo = tipo
        self._datos = datos if datos is not None else {
            "matricula": "5042HZM",
            "dni_adquirente": "35306584C",
            "dni_transmitente": "14958073T",
            "bastidor": "JYA5J09200002507G",
            "cet": "CET-TEST-001",
        }

    async def clasificar(self, ruta: str) -> ResultadoClasificacion:
        return ResultadoClasificacion(
            tipo_detectado=self._tipo,
            confianza_score=0.95,
            confianza_nivel="ALTA",
            datos_extraidos=self._datos,
            justificacion="Mock clasificador",
        )


def _pipeline_con_mock(clf, repo):
    return Pipeline(repo=repo, clasificador=clf)


async def _run_one_cycle(fuente, repo, pipeline):
    task = asyncio.create_task(
        run_email_worker(intervalo=9999, fuente=fuente, repo=repo, pipeline=pipeline)
    )
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def limpiar_estado():
    registro_tramites.reset()
    reset_store()
    yield
    registro_tramites.reset()
    reset_store()


# ── Tests: _construir_tramite_email directamente ───────────────────────────────

def _resultado_pipeline_mock(nombres_clfs: dict):
    """Objeto mínimo que simula un ResultadoPipeline."""
    class _Checklist:
        requisitos_faltantes = []
        requisitos_validos = []
        requisitos_evidencia = []
        requisitos_rechazados = []

    class _Resultado:
        clasificaciones = nombres_clfs
        mensajes_preparados = []
        estado_checklist = _Checklist()
        listo_dgt = True
        no_telematico = False
        error = None

    return _Resultado()


def _deduccion_mock():
    class _D:
        from app.services.catalogo_documental import TipoTramite, SubtipoTramite
        tipo = TipoTramite.TRANSFERENCIA
        subtipo = SubtipoTramite.NINGUNO
        motivo = "mock"
    return _D()


def _email_mock(asunto="Transferencia"):
    adjunto = AdjuntoEmail(nombre="cti.pdf", contenido=b"%PDF-fake", content_type="application/pdf")
    return EmailEntrante(
        message_id="<test-001>",
        remitente="gestoria@test.es",
        asunto=asunto,
        fecha="2026-06-18T09:00:00+00:00",
        adjuntos=[adjunto],
    )


def _clf_resultado(tipo=TipoDocumento.CTI, datos=None):
    if datos is None:
        datos = {"matricula": "5042HZM", "bastidor": "JYA5J09200002507G"}
    return ResultadoClasificacion(
        tipo_detectado=tipo,
        confianza_score=0.95,
        confianza_nivel="ALTA",
        datos_extraidos=datos,
        justificacion="Mock",
    )


def test_documentos_tienen_id_no_nulo():
    """Cada documento creado via email tiene id no nulo."""
    tramite_id = "test-tramite-uuid-0001"
    clfs = {"cti.pdf": _clf_resultado()}
    resultado = _resultado_pipeline_mock(clfs)
    email = _email_mock()
    deduccion = _deduccion_mock()

    tramite = _construir_tramite_email(tramite_id, email, deduccion, resultado)

    assert tramite["documentos"], "No hay documentos en el trámite"
    for doc in tramite["documentos"]:
        assert doc["id"] is not None, f"Documento sin id: {doc}"
        assert doc["id"] != "", "id vacío"


def test_documentos_registrados_en_store():
    """Los documentos quedan en DOCUMENTOS_CARGA tras _construir_tramite_email."""
    tramite_id = "test-tramite-uuid-0002"
    clfs = {"cti.pdf": _clf_resultado(), "modelo620.pdf": _clf_resultado(TipoDocumento.MODELO_620)}
    resultado = _resultado_pipeline_mock(clfs)
    email = _email_mock()
    deduccion = _deduccion_mock()

    _construir_tramite_email(tramite_id, email, deduccion, resultado)

    assert len(DOCUMENTOS_CARGA) == 2, f"Se esperaban 2 docs en store, hay {len(DOCUMENTOS_CARGA)}"
    for doc_id, doc in DOCUMENTOS_CARGA.items():
        assert doc["tramite_id"] == tramite_id
        assert "campos_extraidos" in doc
        assert "justificacion" in doc


def test_doc_ids_formato_correcto():
    """Los ids tienen el formato {tramite_id}-doc-{i}."""
    tramite_id = "test-tramite-uuid-0003"
    clfs = {"a.pdf": _clf_resultado(), "b.pdf": _clf_resultado()}
    resultado = _resultado_pipeline_mock(clfs)

    tramite = _construir_tramite_email(tramite_id, _email_mock(), _deduccion_mock(), resultado)

    doc_ids = [d["id"] for d in tramite["documentos"]]
    assert f"{tramite_id}-doc-0" in doc_ids
    assert f"{tramite_id}-doc-1" in doc_ids


def test_matricula_extraida_de_clasificacion():
    """matrícula se extrae de los datos_extraidos del clasificador."""
    tramite_id = "test-tramite-uuid-0004"
    clfs = {"cti.pdf": _clf_resultado(datos={"matricula": "1234ABC", "bastidor": "WBA99999"})}
    resultado = _resultado_pipeline_mock(clfs)

    tramite = _construir_tramite_email(tramite_id, _email_mock(), _deduccion_mock(), resultado)

    assert tramite["matricula"] == "1234ABC"
    assert tramite["bastidor"] == "WBA99999"


def test_matricula_none_si_no_hay_campos():
    """Sin campos extraídos, matrícula y bastidor son None."""
    tramite_id = "test-tramite-uuid-0005"
    clfs = {"cti.pdf": _clf_resultado(datos={})}
    resultado = _resultado_pipeline_mock(clfs)

    tramite = _construir_tramite_email(tramite_id, _email_mock(), _deduccion_mock(), resultado)

    assert tramite["matricula"] is None
    assert tramite["bastidor"] is None


def test_bastidor_alternativo_num_bastidor():
    """bastidor también se extrae del campo 'num_bastidor'."""
    mat, bas = _extraer_matricula_bastidor({
        "doc.pdf": _clf_resultado(datos={"num_bastidor": "XYZ99999"}),
    })
    assert bas == "XYZ99999"


# ── Tests: API extraccion tras ciclo completo ──────────────────────────────────

@pytest.mark.asyncio
async def test_documentos_accesibles_via_api_tras_email():
    """Tras procesar email, /api/tramites/{id}/documentos devuelve docs con tiene_extraccion=True."""
    crudos = [_email_raw("<msg-docs-001>", adjuntos=[("cti.pdf", b"%PDF-fake")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    clf = ClasificadorMock()
    pipeline = _pipeline_con_mock(clf, repo)

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    assert len(tramites) == 1, "Se esperaba 1 trámite"
    tramite_id = tramites[0]["id"]

    resp = client.get(f"/api/tramites/{tramite_id}/documentos")
    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    docs = resp.json()
    assert len(docs) > 0
    # Al menos un doc debe tener tiene_extraccion=True
    assert any(d["tiene_extraccion"] for d in docs), f"Ningún doc tiene extracción: {docs}"


@pytest.mark.asyncio
async def test_extraccion_doc_accesible_via_api():
    """Un documento del email es accesible en /api/documentos/{doc_id}/extraccion."""
    crudos = [_email_raw("<msg-docs-002>", adjuntos=[("cti.pdf", b"%PDF-fake")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    clf = ClasificadorMock()
    pipeline = _pipeline_con_mock(clf, repo)

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    tramite_id = tramites[0]["id"]

    # Obtener el primer doc con id
    resp_docs = client.get(f"/api/tramites/{tramite_id}/documentos")
    docs = resp_docs.json()
    doc_con_extraccion = next((d for d in docs if d["tiene_extraccion"]), None)
    assert doc_con_extraccion is not None, "No hay documentos con extracción"

    resp_ext = client.get(f"/api/documentos/{doc_con_extraccion['id']}/extraccion")
    assert resp_ext.status_code == 200
    data = resp_ext.json()
    assert data["tramite_id"] == tramite_id
    assert len(data["campos_extraidos"]) > 0


# ── Tests: storage (CAMBIO 4) ──────────────────────────────────────────────────

def test_tiene_archivo_true_tras_guardar():
    """Tras _construir_tramite_email, DOCUMENTOS_CARGA tiene tiene_archivo=True."""
    tramite_id = "test-tramite-uuid-0010"
    adjunto = AdjuntoEmail(nombre="cti.pdf", contenido=b"%PDF-1.4", content_type="application/pdf")
    email_e = EmailEntrante(
        message_id="<test-010>",
        remitente="g@test.es",
        asunto="Test archivo",
        fecha="2026-06-18T10:00:00+00:00",
        adjuntos=[adjunto],
    )
    clfs = {"cti.pdf": _clf_resultado()}
    resultado = _resultado_pipeline_mock(clfs)

    _construir_tramite_email(tramite_id, email_e, _deduccion_mock(), resultado)

    doc_id = f"{tramite_id}-doc-0"
    assert doc_id in DOCUMENTOS_CARGA
    assert DOCUMENTOS_CARGA[doc_id]["tiene_archivo"] is True


def test_archivo_recuperable_via_storage():
    """El archivo guardado por _construir_tramite_email se puede recuperar via storage."""
    from app.services.storage import obtener_archivo

    tramite_id = "test-tramite-uuid-0011"
    contenido_pdf = b"%PDF-1.4 test content"
    adjunto = AdjuntoEmail(nombre="modelo620.pdf", contenido=contenido_pdf, content_type="application/pdf")
    email_e = EmailEntrante(
        message_id="<test-011>",
        remitente="g@test.es",
        asunto="Test storage",
        fecha="2026-06-18T10:00:00+00:00",
        adjuntos=[adjunto],
    )
    clfs = {"modelo620.pdf": _clf_resultado(TipoDocumento.MODELO_620)}
    resultado = _resultado_pipeline_mock(clfs)

    _construir_tramite_email(tramite_id, email_e, _deduccion_mock(), resultado)

    doc_id = f"{tramite_id}-doc-0"
    contenido_leido, mime = obtener_archivo(doc_id)
    assert contenido_leido == contenido_pdf
    assert mime == "application/pdf"


@pytest.mark.asyncio
async def test_tiene_archivo_via_api_endpoint():
    """Tras ciclo completo, /api/documentos/{id}/archivo devuelve el PDF."""
    crudos = [_email_raw("<msg-archivo-001>", adjuntos=[("cti.pdf", b"%PDF-1.4 real")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    clf = ClasificadorMock()
    pipeline = _pipeline_con_mock(clf, repo)

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    tramite_id = tramites[0]["id"]

    resp_docs = client.get(f"/api/tramites/{tramite_id}/documentos")
    docs = resp_docs.json()
    doc_con_archivo = next((d for d in docs if d["tiene_extraccion"]), None)
    assert doc_con_archivo is not None

    resp_archivo = client.get(f"/api/documentos/{doc_con_archivo['id']}/archivo")
    assert resp_archivo.status_code == 200
    assert resp_archivo.headers["content-type"].startswith("application/pdf")
    assert resp_archivo.content == b"%PDF-1.4 real"
