"""Punto de entrada de la aplicación FastAPI de Tyrion."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api.control import router as control_router

app = FastAPI(title="Tyrion", description="Capa de inteligencia documental — Colegio de Gestores")

app.include_router(control_router)

# Servir la Pantalla Control como frontend estático
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_static_dir, "index.html"))
