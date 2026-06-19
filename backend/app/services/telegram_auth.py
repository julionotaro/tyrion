"""Identificación de usuarios de Telegram: admin o gestoría."""
from __future__ import annotations


def identificar_usuario(chat_id: str) -> dict | None:
    """Identifica al usuario por su chat_id de Telegram.

    Returns:
        {"rol": "admin", "nombre": "Administrador", "email": None} si es el admin.
        {"rol": "gestoria", "email": "...", "nombre": "..."} si es una gestoría registrada.
        None si el chat_id no está registrado.
    """
    from app.core.config import get_settings
    from app.services import gestorias

    cfg = get_settings()

    if cfg.telegram_chat_id_admin and chat_id == cfg.telegram_chat_id_admin:
        return {"rol": "admin", "nombre": "Administrador", "email": None}

    g = gestorias.obtener_por_telegram_chat_id(chat_id)
    if g:
        return {
            "rol": "gestoria",
            "nombre": g["nombre"],
            "email": g["email"],
        }

    return None
