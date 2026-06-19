"""Webhook de Telegram: recibe updates y despacha al agente conversacional."""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(update: dict):
    """Recibe updates de Telegram Bot API y los procesa."""
    from app.services.telegram_auth import identificar_usuario
    from app.services.telegram_agent import procesar_mensaje
    from app.services.telegram_sender import enviar_mensaje_telegram

    message = update.get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    texto = (message.get("text") or "").strip()

    if not chat_id or not texto:
        return {"ok": True}

    usuario = identificar_usuario(chat_id)

    if usuario is None:
        respuesta = (
            "Hola 👋 No tengo tu cuenta registrada en el sistema del Colegio de Gestores. "
            "Por favor, contacta con la administración para que te den acceso."
        )
    else:
        respuesta = await procesar_mensaje(chat_id, texto, usuario)

    await enviar_mensaje_telegram(chat_id, respuesta)
    return {"ok": True}


# registrar_webhook() eliminado — se usa polling en vez de webhook (VPS sin HTTPS).
