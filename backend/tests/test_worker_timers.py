"""Tests para worker_timers.py."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _cfg(**kwargs):
    defaults = dict(
        escalado_aviso2_min=30,
        escalado_admin_min=60,
        email_administrativo="admin@test.com",
        telegram_bot_token="",
        telegram_chat_id_admin="",
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _tramite(tid="t-timer-001", minutos_desde_aviso1=0, aviso1_enviado=False):
    """Trámite en pendiente_gestoria con aviso_1 preparado."""
    aviso1_at = (datetime.now(timezone.utc) - timedelta(minutes=minutos_desde_aviso1)).isoformat()
    aviso = {"tipo": "aviso_1", "enviado_at": aviso1_at, "requisito": "cti"}
    if aviso1_enviado:
        aviso["enviado_smtp"] = True
        aviso["enviado_smtp_at"] = aviso1_at
    return {
        "id": tid,
        "estado": "pendiente_gestoria",
        "matricula": "1234 TST",
        "gestoria": "Gestoría Test",
        "gestoria_email": "test@gestoria.com",
        "tipo": "TRANSFERENCIA",
        "documentos_faltantes": ["cti"],
        "historial": [],
        "avisos_pendientes": [aviso],
    }


@pytest.mark.asyncio
async def test_aviso1_no_enviado_llama_smtp():
    """Trámite con aviso_1 preparado pero no enviado → llama enviar_aviso."""
    tramite = _tramite()
    mock_enviar = AsyncMock(return_value=True)
    cfg = _cfg()

    with patch("app.services.smtp_sender.enviar_aviso", mock_enviar), \
         patch("app.core.config.get_settings", return_value=cfg):
        from app.services.worker_timers import _procesar_tramite
        await _procesar_tramite(tramite, cfg)

    mock_enviar.assert_called_once()
    assert tramite["avisos_pendientes"][0].get("enviado_smtp") is True


@pytest.mark.asyncio
async def test_smtp_vacio_no_falla():
    """Con SMTP que devuelve False, el timer no lanza excepción."""
    tramite = _tramite()
    cfg = _cfg(email_administrativo="")

    with patch("app.services.smtp_sender.enviar_aviso", AsyncMock(return_value=False)):
        from app.services.worker_timers import _procesar_tramite
        await _procesar_tramite(tramite, cfg)
    # No debe lanzar excepción


@pytest.mark.asyncio
async def test_aviso2_se_envia_tras_aviso2_min():
    """Aviso_1 enviado hace >aviso2_min → debe enviar aviso_2."""
    tramite = _tramite(minutos_desde_aviso1=35, aviso1_enviado=True)
    mock_enviar = AsyncMock(return_value=True)
    cfg = _cfg()

    with patch("app.services.smtp_sender.enviar_aviso", mock_enviar):
        from app.services.worker_timers import _procesar_tramite
        await _procesar_tramite(tramite, cfg)

    mock_enviar.assert_called_once()
    tipos = [a["tipo"] for a in tramite["avisos_pendientes"]]
    assert "aviso_2" in tipos


@pytest.mark.asyncio
async def test_escalado_se_envia_tras_escalado_min():
    """Aviso_1 enviado hace >escalado_min + aviso_2 existente → envía escalado a admin."""
    tramite = _tramite(minutos_desde_aviso1=70, aviso1_enviado=True)
    # Agregar aviso_2 ya enviado
    aviso2_at = tramite["avisos_pendientes"][0]["enviado_smtp_at"]
    tramite["avisos_pendientes"].append({
        "tipo": "aviso_2", "enviado_smtp": True, "enviado_smtp_at": aviso2_at,
    })
    mock_enviar = AsyncMock(return_value=True)
    cfg = _cfg()

    with patch("app.services.smtp_sender.enviar_aviso", mock_enviar):
        from app.services.worker_timers import _procesar_tramite
        await _procesar_tramite(tramite, cfg)

    mock_enviar.assert_called_once()
    tipos = [a["tipo"] for a in tramite["avisos_pendientes"]]
    assert "escalado" in tipos
