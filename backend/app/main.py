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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Importación diferida para no ejecutar nada al importar main en tests
    from app.services.worker_email import run_email_worker
    task = None
    try:
        task = asyncio.create_task(run_email_worker())
    except Exception:
        logger.warning(
            "Worker email no pudo arrancarse — IMAP puede no estar configurado. "
            "La carga manual sigue funcionando.",
            exc_info=True,
        )
    yield
    if task is not None:
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

# Servir la Pantalla Control como frontend estático
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_static_dir, "index.html"))
