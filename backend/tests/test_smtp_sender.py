"""Tests para smtp_sender.py."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _mock_settings(**kwargs):
    defaults = dict(smtp_host="", smtp_port=465, smtp_user="", smtp_password="", smtp_remitente="")
    defaults.update(kwargs)
    return MagicMock(**defaults)


@pytest.mark.asyncio
async def test_smtp_vacio_retorna_none_sin_excepcion():
    """Si smtp_host está vacío, retorna None sin lanzar excepción."""
    with patch("app.core.config.get_settings", return_value=_mock_settings()):
        from app.services.smtp_sender import enviar_aviso
        result = await enviar_aviso("dest@test.com", "asunto", "<p>html</p>", "texto")
    assert result is None


@pytest.mark.asyncio
async def test_smtp_configurado_envia_ok():
    """Con aiosmtplib mockeado y smtp configurado, retorna un Message-ID string."""
    mock_send = AsyncMock(return_value=None)
    settings = _mock_settings(
        smtp_host="smtp.example.com", smtp_port=465,
        smtp_user="user@example.com", smtp_password="secret",
        smtp_remitente="user@example.com",
    )
    with patch("app.core.config.get_settings", return_value=settings), \
         patch("aiosmtplib.send", mock_send):
        from app.services.smtp_sender import enviar_aviso
        result = await enviar_aviso("dest@test.com", "asunto", "<p>html</p>", "texto")
    assert result is not None
    assert isinstance(result, str)
    assert "@tyrion.colegio" in result
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_error_retorna_none():
    """Si aiosmtplib lanza excepción, retorna None sin relanzar."""
    settings = _mock_settings(
        smtp_host="smtp.example.com", smtp_port=587,
        smtp_user="u", smtp_password="p", smtp_remitente="u@x.com",
    )
    with patch("app.core.config.get_settings", return_value=settings), \
         patch("aiosmtplib.send", AsyncMock(side_effect=Exception("connection refused"))):
        from app.services.smtp_sender import enviar_aviso
        result = await enviar_aviso("dest@test.com", "asunto", "<p>html</p>", "texto")
    assert result is None
