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


async def registrar_webhook() -> None:
    """Registra el webhook de Telegram al arrancar la app."""
    from app.core.config import get_settings
    import httpx

    cfg = get_settings()
    if not cfg.telegram_bot_token or not cfg.tyrion_base_url:
        logger.info(
            "Webhook Telegram no registrado (telegram_bot_token o tyrion_base_url vacíos)."
        )
        return

    webhook_url = f"{cfg.tyrion_base_url.rstrip('/')}/telegram/webhook"
    api_url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/setWebhook"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(api_url, json={"url": webhook_url})
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Webhook Telegram registrado: %s", webhook_url)
            else:
                logger.warning(
                    "No se pudo registrar el webhook Telegram: %s", resp.text[:200]
                )
    except Exception as exc:
        logger.warning("Error registrando webhook Telegram: %s", exc)
