"""Tests para run_telegram_polling."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _cfg(token=""):
    return MagicMock(
        telegram_bot_token=token,
        openai_api_key="sk-test",
        clasificador_openai_model="gpt-4o-mini",
        use_datos_prueba=True,
    )


@pytest.mark.asyncio
async def test_sin_token_no_arranca():
    """Con token vacío, run_telegram_polling retorna inmediatamente sin tocar la red."""
    with patch("app.core.config.get_settings", return_value=_cfg(token="")):
        from app.services.telegram_agent import run_telegram_polling
        # Debe terminar sin lanzar excepción y sin llamadas HTTP
        await run_telegram_polling(intervalo=0)


@pytest.mark.asyncio
async def test_con_token_procesa_update():
    """Con un update disponible, llama al agente y envía respuesta."""
    update = {
        "update_id": 42,
        "message": {
            "chat": {"id": 99999},
            "text": "Hola, estado de mis trámites",
        },
    }
    respuestas = [
        # Primera llamada: devuelve un update
        MagicMock(json=MagicMock(return_value={"ok": True, "result": [update]})),
        # Segunda llamada: lista vacía → bucle se cancela en la tercera iteración
        MagicMock(json=MagicMock(return_value={"ok": True, "result": []})),
    ]

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    mock_http_client.get = AsyncMock(side_effect=respuestas)

    mock_agente = AsyncMock(return_value="Tienes 2 trámites pendientes.")
    mock_enviar = AsyncMock(return_value=True)
    usuario = {"rol": "gestoria", "nombre": "G. Test", "email": "t@test.es"}

    with patch("app.core.config.get_settings", return_value=_cfg(token="123:ABC")), \
         patch("httpx.AsyncClient", return_value=mock_http_client), \
         patch("app.services.telegram_auth.identificar_usuario", return_value=usuario), \
         patch("app.services.telegram_agent.procesar_mensaje", mock_agente), \
         patch("app.services.telegram_sender.enviar_mensaje_telegram", mock_enviar):

        from app.services.telegram_agent import run_telegram_polling
        task = asyncio.create_task(run_telegram_polling(intervalo=0))
        # Dejar que procese el primer ciclo
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_agente.assert_called_once()
    mock_enviar.assert_called_once()
    # El offset debe haberse avanzado: siguiente getUpdates con offset=43
    second_call_params = mock_http_client.get.call_args_list[1].kwargs.get(
        "params", mock_http_client.get.call_args_list[1][1].get("params", {})
    )
    assert second_call_params.get("offset") == 43


@pytest.mark.asyncio
async def test_usuario_desconocido_recibe_mensaje_no_registrado():
    """Chat_id no registrado → respuesta de no acceso, no llama al agente."""
    update = {
        "update_id": 1,
        "message": {"chat": {"id": 77777}, "text": "hola"},
    }
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    # Primera respuesta con update, luego vacía para que el bucle no repita
    mock_http_client.get = AsyncMock(side_effect=[
        MagicMock(json=MagicMock(return_value={"ok": True, "result": [update]})),
        MagicMock(json=MagicMock(return_value={"ok": True, "result": []})),
        asyncio.CancelledError(),
    ])
    mock_agente = AsyncMock(return_value="respuesta")
    mock_enviar = AsyncMock(return_value=True)

    with patch("app.core.config.get_settings", return_value=_cfg(token="tok")), \
         patch("httpx.AsyncClient", return_value=mock_http_client), \
         patch("app.services.telegram_auth.identificar_usuario", return_value=None), \
         patch("app.services.telegram_agent.procesar_mensaje", mock_agente), \
         patch("app.services.telegram_sender.enviar_mensaje_telegram", mock_enviar):

        from app.services.telegram_agent import run_telegram_polling
        try:
            await run_telegram_polling(intervalo=0)
        except asyncio.CancelledError:
            pass

    mock_agente.assert_not_called()
    assert mock_enviar.call_count == 1
    texto_enviado = mock_enviar.call_args[0][1]
    assert "registrad" in texto_enviado.lower() or "acceso" in texto_enviado.lower()
