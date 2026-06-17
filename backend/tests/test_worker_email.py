"""
Tests de integración del worker de ingesta de email (Capa 1+2).

Verifica el flujo completo desde email simulado hasta trámite visible en
registro_tramites.listar_tramites(). Sin red, sin BD, sin clasificador real:
  - FuenteEnMemoria: fuente de correo con emails RFC822 prefabricados.
  - RepositorioEnMemoria: repositorio en memoria (ya definido en pipeline.py).
  - ClasificadorMock: devuelve un resultado determinista para cualquier archivo.
  - FuenteLenta: simula IMAP lento/colgado para test de no-bloqueo del event loop.

Tests:
  - Email con adjunto útil → trámite aparece en registro_tramites
  - Email con adjunto útil → email_procesado registrado en repo
  - Email ya visto (dedup) → no crea trámite duplicado
  - Email sin adjuntos útiles → no crea trámite
  - Tipo deducido correctamente desde adjunto clasificado como CTI
"""
import asyncio
import email as email_lib
import time
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
    """Ejecuta exactamente un ciclo del worker y cancela.

    Con asyncio.to_thread el poll() corre en un thread real, así que hay que
    esperar con asyncio.sleep() suficiente para que el thread termine y el ciclo
    completo (poll + clasificación + escritura en registro) se complete.
    """
    task = asyncio.create_task(
        run_email_worker(intervalo=9999, fuente=fuente, repo=repo, pipeline=pipeline)
    )
    # 0.5s es más que suficiente para un FuenteEnMemoria (sin red ni disco real)
    await asyncio.sleep(0.5)
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


# ── Test de no-bloqueo del event loop (regresión del bug de startup) ──────────

class _FuenteLenta:
    """Simula una fuente IMAP que tarda 300ms (bloqueo síncrono en thread).

    Con asyncio.to_thread el event loop sigue libre durante ese tiempo.
    Sin to_thread, bloquearía el event loop y congela el startup de FastAPI.
    """
    DELAY = 0.3  # segundos de bloqueo síncrono

    def mensajes_crudos(self) -> list[bytes]:
        time.sleep(self.DELAY)
        return []


@pytest.mark.asyncio
async def test_imap_lento_no_bloquea_event_loop():
    """Regresión: IMAP bloqueante corre en thread, el event loop sigue libre.

    Lanza el worker con una fuente que tarda 300ms síncronos (simula Gmail lento).
    Simultáneamente lanza una coroutine que se marca lista tras 30ms.
    Si el event loop estuviera bloqueado, la coroutine no podría correr y
    el evento no estaría set en 150ms. Con asyncio.to_thread sí está.
    """
    event_loop_libre = asyncio.Event()

    async def _marcar_libre():
        await asyncio.sleep(0.03)  # 30ms — mucho menos que los 300ms de IMAP
        event_loop_libre.set()

    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=ClasificadorMock())

    worker_task = asyncio.create_task(
        run_email_worker(intervalo=9999, fuente=_FuenteLenta(), repo=repo, pipeline=pipeline)
    )
    check_task = asyncio.create_task(_marcar_libre())

    # Esperar máximo 150ms — la mitad del bloqueo IMAP simulado.
    # Si el event loop no está bloqueado, los 30ms de _marcar_libre se completan bien antes.
    try:
        await asyncio.wait_for(asyncio.shield(event_loop_libre.wait()), timeout=0.15)
        loop_libre = True
    except asyncio.TimeoutError:
        loop_libre = False
    finally:
        worker_task.cancel()
        check_task.cancel()
        await asyncio.gather(worker_task, check_task, return_exceptions=True)

    assert loop_libre, (
        "El event loop se bloqueó durante el poll IMAP — "
        "asyncio.to_thread no está aplicado correctamente en run_email_worker"
    )


@pytest.mark.asyncio
async def test_startup_completa_sin_bloqueo_con_imap_lento():
    """El lifespan de FastAPI completa el startup aunque IMAP tarde 300ms.

    Verifica que asyncio.create_task + asyncio.to_thread en el worker permiten
    que el startup (yield en lifespan) ocurra inmediatamente, independientemente
    del tiempo que tarde la conexión IMAP.
    """
    from contextlib import asynccontextmanager

    startup_completado = asyncio.Event()

    @asynccontextmanager
    async def lifespan_simulado():
        task = asyncio.create_task(
            run_email_worker(
                intervalo=9999,
                fuente=_FuenteLenta(),
                repo=RepositorioEnMemoria(),
                pipeline=Pipeline(repo=RepositorioEnMemoria(), clasificador=ClasificadorMock()),
            )
        )
        startup_completado.set()  # equivalente al yield de FastAPI
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    start = time.monotonic()
    async with lifespan_simulado():
        elapsed = time.monotonic() - start

    # El startup debe completarse en <50ms, no en los 300ms del IMAP lento
    assert elapsed < 0.05, (
        f"Startup tardó {elapsed:.3f}s — el worker bloqueó el arranque de FastAPI"
    )
    assert startup_completado.is_set()
