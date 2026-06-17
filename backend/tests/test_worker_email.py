"""
Tests de integración del worker de ingesta de email (Capa 1+2).

Verifica el flujo completo desde email simulado hasta trámite visible en
registro_tramites.listar_tramites(). Sin red, sin BD, sin clasificador real:
  - FuenteEnMemoria: fuente de correo con emails RFC822 prefabricados.
  - RepositorioEnMemoria: repositorio en memoria (ya definido en pipeline.py).
  - ClasificadorMock: devuelve un resultado determinista para cualquier archivo.

Tests:
  - Email con adjunto útil → trámite aparece en registro_tramites
  - Email con adjunto útil → email_procesado registrado en repo
  - Email ya visto (dedup) → no crea trámite duplicado
  - Email sin adjuntos útiles → no crea trámite
  - Tipo deducido correctamente desde adjunto clasificado como CTI
"""
import asyncio
import email as email_lib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from app.services import registro_tramites
from app.services.catalogo_documental import TipoDocumento
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services.worker_email import run_email_worker
from app.schemas.clasificacion import ResultadoClasificacion


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_raw(
    message_id: str,
    remitente: str = "gestoria@example.com",
    asunto: str = "Documentos trámite",
    adjuntos: list[tuple[str, bytes]] | None = None,
) -> bytes:
    msg = MIMEMultipart()
    msg["Message-ID"] = message_id
    msg["From"] = remitente
    msg["Subject"] = asunto
    msg["Date"] = "Tue, 17 Jun 2026 09:00:00 +0000"
    msg.attach(MIMEText("Adjunto documentación.", "plain"))
    for nombre, contenido in (adjuntos or []):
        parte = MIMEApplication(contenido, Name=nombre)
        parte["Content-Disposition"] = f'attachment; filename="{nombre}"'
        msg.attach(parte)
    return msg.as_bytes()


class FuenteEnMemoria:
    """Fuente de correo sin red — devuelve lista fija de emails crudos."""
    def __init__(self, crudos: list[bytes]):
        self._crudos = crudos

    def mensajes_crudos(self) -> list[bytes]:
        return self._crudos


class ClasificadorMock:
    """Clasificador que devuelve siempre el tipo indicado, confianza ALTA."""
    def __init__(self, tipo: TipoDocumento = TipoDocumento.CTI):
        self._tipo = tipo

    async def clasificar(self, ruta: str) -> ResultadoClasificacion:
        return ResultadoClasificacion(
            tipo_detectado=self._tipo,
            confianza_score=0.95,
            confianza_nivel="ALTA",
            datos_extraidos={
                "matricula": "1234ABC",
                "titular": "Juan García",
                "bastidor": "WBA12345",
                "cet": "CET-TEST-001",
            },
            justificacion="Mock clasificador",
        )


async def _run_one_cycle(fuente, repo, pipeline):
    """Ejecuta exactamente un ciclo del worker y cancela."""
    task = asyncio.create_task(
        run_email_worker(intervalo=0, fuente=fuente, repo=repo, pipeline=pipeline)
    )
    await asyncio.sleep(0)   # cede control para que el worker ejecute el ciclo
    await asyncio.sleep(0)   # segunda cesión para clasificaciones async
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def limpiar_registro():
    registro_tramites.reset()
    yield
    registro_tramites.reset()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_email_con_adjunto_crea_tramite_en_registro():
    """Email con adjunto PDF → trámite visible en registro_tramites."""
    crudos = [_email_raw("<msg-001@test>", adjuntos=[("cti.pdf", b"%PDF-fake")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    clf = ClasificadorMock(TipoDocumento.CTI)
    pipeline = Pipeline(repo=repo, clasificador=clf)

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    assert len(tramites) == 1
    t = tramites[0]
    assert t["origen"] == "email"
    assert t["gestoria_email"] == "gestoria@example.com"
    assert t["tipo"] == "TRANSFERENCIA"  # CTI → TRANSFERENCIA


@pytest.mark.asyncio
async def test_email_con_adjunto_registra_email_procesado():
    """Email procesado queda en el repositorio (dedup persistente)."""
    crudos = [_email_raw("<msg-002@test>", adjuntos=[("cti.pdf", b"%PDF-fake")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock())

    await _run_one_cycle(fuente, repo, pipeline)

    ids_vistos = repo.mensaje_ids_procesados()
    assert "<msg-002@test>" in ids_vistos


@pytest.mark.asyncio
async def test_email_ya_visto_no_genera_tramite_duplicado():
    """Si el Message-ID ya está en vistos, el email no se procesa de nuevo."""
    raw = _email_raw("<msg-dup@test>", adjuntos=[("cti.pdf", b"%PDF-fake")])
    fuente = FuenteEnMemoria([raw])
    repo = RepositorioEnMemoria()
    # Pre-marcar como visto
    from app.models.persistencia import EmailProcesado, EstadoEmail
    from datetime import datetime
    repo.guardar_email_procesado(EmailProcesado(
        message_id="<msg-dup@test>",
        remitente="gestoria@example.com",
        asunto="Documentos trámite",
        fecha_recibido=datetime.utcnow(),
        num_adjuntos=1,
        estado=EstadoEmail.PROCESADO,
    ))
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock())

    await _run_one_cycle(fuente, repo, pipeline)

    assert len(registro_tramites.listar_tramites()) == 0


@pytest.mark.asyncio
async def test_email_sin_adjuntos_utiles_no_crea_tramite():
    """Email sin adjuntos soportados no genera trámite."""
    raw = _email_raw("<msg-sin-adj@test>", adjuntos=[])
    fuente = FuenteEnMemoria([raw])
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock())

    await _run_one_cycle(fuente, repo, pipeline)

    assert len(registro_tramites.listar_tramites()) == 0


@pytest.mark.asyncio
async def test_tipo_deducido_desde_clasificacion_cti():
    """Adjunto clasificado como CTI → trámite tipo TRANSFERENCIA."""
    crudos = [_email_raw("<msg-cti@test>", adjuntos=[("cambio_titularidad.pdf", b"%PDF")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock(TipoDocumento.CTI))

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    assert len(tramites) == 1
    assert tramites[0]["tipo"] == "TRANSFERENCIA"
    assert tramites[0]["subtipo"] == "ninguno"


@pytest.mark.asyncio
async def test_carga_manual_no_afectada_por_worker():
    """La carga manual sigue funcionando independientemente del worker."""
    # Simular tramite de carga manual ya existente
    registro_tramites.agregar_tramite({
        "id": "tramite-manual-001",
        "tipo": "TRANSFERENCIA",
        "subtipo": "ninguno",
        "matricula": "9999ZZZ",
        "bastidor": "MANUAL123",
        "gestoria": "Gestoría Test",
        "gestoria_email": "test@gestoria.com",
        "estado": "listo_dgt",
        "fecha_entrada": "2026-06-17T10:00:00+00:00",
        "alerta": False,
        "origen": "carga_manual",
        "documentos": [],
        "historial": [],
        "avisos_pendientes": [],
        "documentos_faltantes": [],
    })

    crudos = [_email_raw("<msg-coexist@test>", adjuntos=[("cti.pdf", b"%PDF")])]
    fuente = FuenteEnMemoria(crudos)
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock())

    await _run_one_cycle(fuente, repo, pipeline)

    tramites = registro_tramites.listar_tramites()
    assert len(tramites) == 2
    origenes = {t["origen"] for t in tramites}
    assert origenes == {"carga_manual", "email"}
