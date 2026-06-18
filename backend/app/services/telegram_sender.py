"""Envío de mensajes vía Telegram Bot API (httpx, sin librerías adicionales)."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def enviar_mensaje_telegram(chat_id: str, texto: str) -> bool:
    """Envía un mensaje via Telegram Bot API. Retorna True si OK, False si falla."""
    from app.core.config import get_settings
    cfg = get_settings()

    if not cfg.telegram_bot_token:
        return False

    url = _TELEGRAM_API.format(token=cfg.telegram_bot_token)
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram OK → chat_id=%s", chat_id)
                return True
            logger.error("Telegram error %s: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.error("Telegram excepción: %s", exc)
        return False
