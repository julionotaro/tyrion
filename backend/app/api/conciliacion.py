"""Router de Conciliación diaria.

Cruza planilla (Tempus) × expedientes (registro_tramites) × hoja de caja (SAGE)
por gestoría y día. Carga de planilla y hoja de caja vía PDF; vista conciliada
vía GET; aviso a gestorías vía POST.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api import store
from app.services import gestorias
from app.services.conciliacion import conciliar
from app.services.ingesta_hoja_caja import parse_hoja_caja_pdf
from app.services.ingesta_planilla import parse_planilla_pdf
from app.services.registro_tramites import listar_tramites

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conciliacion", tags=["conciliacion"])


def _clave(fecha: date, tipo: str) -> str:
    return f"{fecha.isoformat()}|{tipo}"


def _parse_fecha(fecha_str: str | None) -> date:
    if not fecha_str:
        return date.today()
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida, usar YYYY-MM-DD")


# ── Carga de planilla ─────────────────────────────────────────────────────────

@router.post("/planilla")
async def cargar_planilla(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    try:
        planilla = parse_planilla_pdf(contenido)
    except Exception as exc:
        logger.error("Error parseando planilla PDF: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"No se pudo parsear la planilla: {exc}")

    tipo = planilla.tipo.value if hasattr(planilla.tipo, "value") else str(planilla.tipo)
    clave = _clave(planilla.fecha, tipo)
    store.PLANILLAS_DIA[clave] = planilla
    return {
        "id": clave,
        "fecha": planilla.fecha.isoformat(),
        "tipo": tipo,
        "tramites": len(planilla),
    }


# ── Carga de hoja de caja ─────────────────────────────────────────────────────

@router.post("/hoja-caja")
async def cargar_hoja_caja(
    archivo: UploadFile = File(...),
    gestoria_email: str = Form(""),
):
    contenido = await archivo.read()
    try:
        hoja = parse_hoja_caja_pdf(contenido, gestoria_email=gestoria_email)
    except Exception as exc:
        logger.error("Error parseando hoja de caja PDF: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"No se pudo parsear la hoja de caja: {exc}")

    store.HOJAS_CAJA[hoja.fecha.isoformat()] = hoja
    return {
        "fecha": hoja.fecha.isoformat(),
        "total": hoja.total,
        "lineas": len(hoja.lineas),
    }


# ── Vista conciliada ──────────────────────────────────────────────────────────

@router.get("")
def obtener_conciliacion(fecha: str | None = None, tipo: str = "TRANSFERENCIA"):
    f = _parse_fecha(fecha)
    planilla = store.PLANILLAS_DIA.get(_clave(f, tipo))
    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay planilla cargada para {f.isoformat()} / {tipo}",
        )

    hoja = store.HOJAS_CAJA.get(f.isoformat())
    expedientes = listar_tramites()
    conc = conciliar(planilla, expedientes, hoja)

    return {
        "fecha": conc.fecha.isoformat(),
        "tipo": conc.tipo,
        "total": conc.total,
        "cuadrados": conc.cuadrados,
        "pendientes": conc.pendientes,
        "sin_expediente": conc.sin_expediente,
        "filas": [
            {**asdict(fila), "estado": fila.estado.value}
            for fila in conc.filas
        ],
        "descuadre_caja": asdict(conc.descuadre_caja) if conc.descuadre_caja else None,
    }


# ── Aviso a gestorías ─────────────────────────────────────────────────────────

@router.post("/avisar")
async def avisar_gestorias(payload: dict):
    matriculas = payload.get("matriculas") or []
    mensaje = payload.get("mensaje") or "Hay trámites pendientes de documentación en la conciliación del día."
    if not matriculas:
        raise HTTPException(status_code=400, detail="No se indicaron matrículas a avisar")

    from app.services.smtp_sender import enviar_aviso

    # Reunir gestorías destino a partir de los expedientes que cruzan esas matrículas
    expedientes = listar_tramites()
    emails_destino: set[str] = set()
    for exp in expedientes:
        ids = exp.get("identificadores") or {}
        mat = (ids.get("matricula") or exp.get("matricula") or "").upper().replace(" ", "").replace("-", "")
        for m in matriculas:
            mn = (m or "").upper().replace(" ", "").replace("-", "")
            if mat and mat == mn:
                email = exp.get("gestoria_email")
                if email:
                    emails_destino.add(email)

    avisadas = 0
    for email in emails_destino:
        g = gestorias.obtener(email)
        nombre = g["nombre"] if g else email
        cuerpo = f"<p>Hola {nombre},</p><p>{mensaje}</p>"
        try:
            res = await enviar_aviso(
                destinatario=email,
                asunto="Conciliación diaria — documentación pendiente",
                cuerpo_html=cuerpo,
                cuerpo_texto=mensaje,
            )
            if res:
                avisadas += 1
        except Exception as exc:
            logger.warning("No se pudo avisar a %s: %s", email, exc)

    return {"avisadas": avisadas, "destinos": list(emails_destino)}
