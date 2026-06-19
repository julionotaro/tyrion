"""Endpoints CRUD para gestorías.

GET    /api/gestorias          — listar todas
POST   /api/gestorias          — crear nueva
PUT    /api/gestorias/{email}  — actualizar
DELETE /api/gestorias/{email}  — eliminar
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import gestorias as store

router = APIRouter(prefix="/api/gestorias", tags=["gestorias"])


class GestoriaIn(BaseModel):
    email: str
    nombre: str
    contacto: str = ""
    telefono: str = ""
    telegram_chat_id: str = ""


class GestoriaUpdate(BaseModel):
    nombre: str | None = None
    contacto: str | None = None
    telefono: str | None = None
    telegram_chat_id: str | None = None


@router.get("")
def listar_gestorias():
    return store.listar()


@router.post("", status_code=201)
def crear_gestoria(payload: GestoriaIn):
    try:
        return store.crear(
            email=payload.email,
            nombre=payload.nombre,
            contacto=payload.contacto,
            telefono=payload.telefono,
            telegram_chat_id=payload.telegram_chat_id,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.put("/{email:path}")
def actualizar_gestoria(email: str, payload: GestoriaUpdate):
    try:
        return store.actualizar(
            email=email,
            nombre=payload.nombre,
            contacto=payload.contacto,
            telefono=payload.telefono,
            telegram_chat_id=payload.telegram_chat_id,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{email:path}", status_code=204)
def eliminar_gestoria(email: str):
    try:
        store.eliminar(email)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
