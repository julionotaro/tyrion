"""Punto de entrada de la aplicación FastAPI de Tyrion."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.control import router as control_router
from app.api.documentos import router as documentos_router
from app.api.carga import router as carga_router
from app.api.gestorias_api import router as gestorias_router
from app.api.telegram_webhook import router as telegram_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Importación diferida para no ejecutar nada al importar main en tests
    from app.services.worker_email import run_email_worker
    from app.services.worker_timers import run_timer_worker
    from app.services.telegram_agent import run_telegram_polling
    tasks = []
    try:
        tasks.append(asyncio.create_task(run_email_worker()))
    except Exception:
        logger.warning(
            "Worker email no pudo arrancarse — IMAP puede no estar configurado. "
            "La carga manual sigue funcionando.",
            exc_info=True,
        )
    try:
        tasks.append(asyncio.create_task(run_timer_worker()))
    except Exception:
        logger.warning("Worker timers no pudo arrancarse.", exc_info=True)
    try:
        tasks.append(asyncio.create_task(run_telegram_polling()))
    except Exception:
        logger.warning("Telegram polling no pudo arrancarse.", exc_info=True)
    yield
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Tyrion",
    description="Capa de inteligencia documental — Colegio de Gestores",
    lifespan=lifespan,
)

app.include_router(control_router)
app.include_router(documentos_router)
app.include_router(carga_router)
app.include_router(gestorias_router)
app.include_router(telegram_router)

# Servir la Pantalla Control como frontend estático
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_static_dir, "index.html"))
