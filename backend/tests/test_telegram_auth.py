"""Tests para telegram_auth.py."""
import pytest
from unittest.mock import patch, MagicMock


def _cfg(admin_chat_id="999999"):
    return MagicMock(telegram_chat_id_admin=admin_chat_id, telegram_bot_token="tok")


def test_admin_identificado_por_chat_id():
    with patch("app.core.config.get_settings", return_value=_cfg("111111")):
        from app.services.telegram_auth import identificar_usuario
        u = identificar_usuario("111111")
    assert u is not None
    assert u["rol"] == "admin"


def test_gestoria_identificada_por_chat_id():
    from app.services import gestorias
    gestorias.reset()
    # Registrar chat_id en una gestoría
    gestorias.actualizar("ruiz@gestorias.es", telegram_chat_id="777777")

    with patch("app.core.config.get_settings", return_value=_cfg("999999")):
        from app.services.telegram_auth import identificar_usuario
        u = identificar_usuario("777777")

    gestorias.reset()
    assert u is not None
    assert u["rol"] == "gestoria"
    assert "ruiz@gestorias.es" in u["email"]


def test_chat_id_desconocido_retorna_none():
    from app.services import gestorias
    gestorias.reset()
    with patch("app.core.config.get_settings", return_value=_cfg("111111")):
        from app.services.telegram_auth import identificar_usuario
        u = identificar_usuario("000000")
    assert u is None


def test_admin_no_confunde_con_gestoria():
    """El admin_chat_id tiene prioridad sobre cualquier chat_id de gestoría."""
    from app.services import gestorias
    gestorias.reset()
    gestorias.actualizar("ruiz@gestorias.es", telegram_chat_id="ADMIN_ID")

    with patch("app.core.config.get_settings", return_value=_cfg("ADMIN_ID")):
        from app.services.telegram_auth import identificar_usuario
        u = identificar_usuario("ADMIN_ID")

    gestorias.reset()
    # Admin tiene prioridad
    assert u["rol"] == "admin"
