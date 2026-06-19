"""Tests para telegram_agent.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _cfg(api_key="sk-test", use_datos_prueba=True):
    return MagicMock(
        openai_api_key=api_key,
        clasificador_openai_model="gpt-4o-mini",
        use_datos_prueba=use_datos_prueba,
    )


def _mock_openai_response(text="Respuesta de prueba."):
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_sin_api_key_retorna_mensaje_error():
    with patch("app.core.config.get_settings", return_value=_cfg(api_key="")):
        from app.services.telegram_agent import procesar_mensaje
        resp = await procesar_mensaje("123", "hola", {"rol": "admin", "nombre": "Admin"})
    assert "no está disponible" in resp.lower() or "sin clave" in resp.lower()


@pytest.mark.asyncio
async def test_admin_obtiene_respuesta():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response("Hoy hay 5 trámites pendientes.")
    )
    usuario = {"rol": "admin", "nombre": "Administrador", "email": None}

    with patch("app.core.config.get_settings", return_value=_cfg()), \
         patch("openai.AsyncOpenAI", return_value=mock_client):
        from app.services.telegram_agent import procesar_mensaje
        resp = await procesar_mensaje("111", "Dame un resumen del día", usuario)

    assert isinstance(resp, str)
    assert len(resp) > 0
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_gestoria_solo_ve_sus_tramites():
    """El system prompt debe incluir solo los trámites de la gestoría."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response("Tienes 1 trámite pendiente.")
    )
    usuario = {
        "rol": "gestoria",
        "nombre": "Gestoría Test",
        "email": "test@gest.es",
    }

    with patch("app.core.config.get_settings", return_value=_cfg()), \
         patch("openai.AsyncOpenAI", return_value=mock_client):
        from app.services.telegram_agent import procesar_mensaje
        resp = await procesar_mensaje("222", "Cuántos trámites tengo", usuario)

    assert isinstance(resp, str)
    # Verificar que el system_prompt pasado al cliente contiene la identificación
    call_kwargs = mock_client.chat.completions.create.call_args
    system = call_kwargs.kwargs["messages"][0]["content"]
    assert "gestoria" in system
    assert "Gestoría Test" in system or "test@gest.es" in system


@pytest.mark.asyncio
async def test_respuesta_de_error_no_propaga_excepcion():
    """Si OpenAI falla, devuelve mensaje amable sin lanzar excepción."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API down"))
    usuario = {"rol": "admin", "nombre": "Admin", "email": None}

    with patch("app.core.config.get_settings", return_value=_cfg()), \
         patch("openai.AsyncOpenAI", return_value=mock_client):
        from app.services.telegram_agent import procesar_mensaje
        resp = await procesar_mensaje("333", "hola", usuario)

    assert "lo siento" in resp.lower() or "no puedo" in resp.lower()
