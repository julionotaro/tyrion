"""Tests para telegram_sender.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_settings(**kwargs):
    defaults = dict(telegram_bot_token="", telegram_chat_id_admin="")
    defaults.update(kwargs)
    return MagicMock(**defaults)


@pytest.mark.asyncio
async def test_token_vacio_retorna_false():
    """Sin token configurado, retorna False silenciosamente."""
    with patch("app.core.config.get_settings", return_value=_mock_settings()):
        from app.services.telegram_sender import enviar_mensaje_telegram
        result = await enviar_mensaje_telegram("123456", "texto")
    assert result is False


@pytest.mark.asyncio
async def test_con_token_envia_ok():
    """Con token y httpx mockeado (status 200), retorna True."""
    mock_response = MagicMock(status_code=200)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    settings = _mock_settings(telegram_bot_token="123:ABC", telegram_chat_id_admin="-100123")
    with patch("app.core.config.get_settings", return_value=settings), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from app.services.telegram_sender import enviar_mensaje_telegram
        result = await enviar_mensaje_telegram("-100123", "⚠️ Escalado test")
    assert result is True


@pytest.mark.asyncio
async def test_error_http_retorna_false():
    """Si httpx lanza excepción, retorna False sin relanzar."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=Exception("network error"))

    settings = _mock_settings(telegram_bot_token="123:ABC")
    with patch("app.core.config.get_settings", return_value=settings), \
         patch("httpx.AsyncClient", return_value=mock_client):
        from app.services.telegram_sender import enviar_mensaje_telegram
        result = await enviar_mensaje_telegram("123", "texto")
    assert result is False
