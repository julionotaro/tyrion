"""Envío de emails salientes via SMTP (aiosmtplib)."""
from __future__ import annotations

import logging
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def enviar_aviso(
    destinatario: str,
    asunto: str,
    cuerpo_html: str,
    cuerpo_texto: str,
) -> str | None:
    """Envía un email via SMTP.

    Retorna el Message-ID del aviso enviado si OK, None si falla.
    El Message-ID se genera internamente para permitir la correlación de respuestas.
    """
    from app.core.config import get_settings
    cfg = get_settings()

    if not cfg.smtp_host:
        logger.warning("SMTP no configurado (smtp_host vacío) — aviso NO enviado a %s.", destinatario)
        return None

    try:
        import aiosmtplib
    except ImportError:
        logger.error("aiosmtplib no instalado — aviso NO enviado a %s.", destinatario)
        return None

    remitente = cfg.smtp_remitente or cfg.smtp_user
    message_id = f"<{uuid.uuid4()}@tyrion.colegio>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario
    msg["Message-ID"] = message_id
    msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    use_tls = cfg.smtp_port == 465

    try:
        if use_tls:
            await aiosmtplib.send(
                msg,
                hostname=cfg.smtp_host,
                port=cfg.smtp_port,
                use_tls=True,
                username=cfg.smtp_user,
                password=cfg.smtp_password,
            )
        else:
            await aiosmtplib.send(
                msg,
                hostname=cfg.smtp_host,
                port=cfg.smtp_port,
                start_tls=True,
                username=cfg.smtp_user,
                password=cfg.smtp_password,
            )
        logger.info("Aviso enviado OK → %s (%s) [%s]", destinatario, asunto, message_id)
        return message_id
    except Exception as exc:
        logger.error("Error enviando aviso a %s: %s", destinatario, exc)
        return None
