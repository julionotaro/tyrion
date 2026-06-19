"""Tests para el webhook de Telegram."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _update(chat_id: str, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": int(chat_id) if chat_id.isdigit() else chat_id, "type": "private"},
            "from": {"id": int(chat_id) if chat_id.isdigit() else chat_id, "first_name": "Test"},
            "text": text,
        }
    }


def test_update_sin_texto_retorna_ok():
    resp = client.post("/telegram/webhook", json={"update_id": 1, "message": {"chat": {"id": 123}}})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_update_chat_id_desconocido_responde_no_registrado():
    mock_enviar = AsyncMock(return_value=True)
    with patch("app.services.telegram_auth.identificar_usuario", return_value=None), \
         patch("app.services.telegram_sender.enviar_mensaje_telegram", mock_enviar):
        resp = client.post("/telegram/webhook", json=_update("000000", "hola"))

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_enviar.assert_called_once()
    # El mensaje debe mencionar "no" y "registrado" (en cualquier variante)
    args = mock_enviar.call_args
    texto_enviado = args[0][1] if args[0] else args.kwargs.get("texto", "")
    assert "registrad" in texto_enviado.lower() or "acceso" in texto_enviado.lower()


def test_update_valido_llama_agente():
    mock_agente = AsyncMock(return_value="Tienes 2 trámites pendientes.")
    mock_enviar = AsyncMock(return_value=True)
    usuario = {"rol": "gestoria", "nombre": "G. Test", "email": "t@test.es"}

    with patch("app.services.telegram_auth.identificar_usuario", return_value=usuario), \
         patch("app.services.telegram_agent.procesar_mensaje", mock_agente), \
         patch("app.services.telegram_sender.enviar_mensaje_telegram", mock_enviar):
        resp = client.post("/telegram/webhook", json=_update("12345", "Cómo van mis trámites"))

    assert resp.status_code == 200
    mock_agente.assert_called_once()
    mock_enviar.assert_called_once()
