"""Watches a directory for Tempus CSV exports and ingests them automatically."""
import asyncio
import logging
import shutil
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.services.ingesta_planilla import parse_relacion_transmisiones, parse_relacion_matriculas

logger = logging.getLogger(__name__)


def _watch_dir() -> Path:
    s = get_settings()
    d = Path(getattr(s, "watch_dir", "/tmp/tyrion_watch"))
    d.mkdir(parents=True, exist_ok=True)
    (d / "procesados").mkdir(exist_ok=True)
    return d


def procesar_archivo(ruta: Path, repo=None) -> int:
    """Parses a CSV file, saves planilla. Returns number of tramites."""
    nombre = ruta.name.lower()
    contenido = ruta.read_text(encoding="utf-8", errors="replace")

    if nombre.startswith("transmisiones"):
        planilla = parse_relacion_transmisiones(contenido, fecha=date.today())
    elif nombre.startswith("matriculas"):
        planilla = parse_relacion_matriculas(contenido, fecha=date.today())
    else:
        logger.warning("Archivo ignorado (patron desconocido): %s", ruta.name)
        return 0

    if repo:
        planilla_id = repo.guardar_planilla_dia(planilla)
        for tp in planilla.tramites:
            repo.guardar_tramite_planificado(tp, planilla_id)

    # Move to procesados/
    destino = ruta.parent / "procesados" / ruta.name
    shutil.move(str(ruta), str(destino))

    logger.info("Planilla detectada: %d tramites cargados desde %s", len(planilla.tramites), ruta.name)
    return len(planilla.tramites)


async def run_watcher(intervalo: int = 60, repo=None):
    """Periodic task that checks for new CSV files."""
    logger.info("Watcher planilla iniciado (intervalo=%ds)", intervalo)
    while True:
        watch_dir = _watch_dir()
        for ruta in sorted(watch_dir.glob("*.csv")):
            try:
                n = procesar_archivo(ruta, repo=repo)
                if n > 0:
                    logger.info("Procesado %s: %d tramites", ruta.name, n)
            except Exception as exc:
                logger.error("Error procesando %s: %s", ruta.name, exc)
        await asyncio.sleep(intervalo)
