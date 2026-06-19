"""Worker de timers: revisa avisos pendientes y dispara SMTP + Telegram.

Lógica por trámite en estado pendiente_gestoria:
  T+0  → aviso_1 preparado y no enviado → enviar por SMTP a gestoría
  T+aviso2_min desde aviso_1 → enviar aviso_2
  T+escalado_min desde aviso_1 → enviar escalado a email_administrativo + Telegram
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _minutos_desde(ts: datetime) -> float:
    return (_ahora() - ts).total_seconds() / 60


async def _procesar_tramite(tramite: dict, cfg) -> None:
    """Revisa y dispara los avisos correspondientes para un único trámite."""
    from app.services.smtp_sender import enviar_aviso
    from app.services.telegram_sender import enviar_mensaje_telegram
    from app.services.aviso_templates import aviso_1, aviso_2, escalado_admin

    tid = tramite.get("id", "?")
    matricula = tramite.get("matricula") or tid
    gestoria = tramite.get("gestoria") or "gestoría"
    gestoria_email = tramite.get("gestoria_email", "")
    tipo = tramite.get("tipo", "TRAMITE")
    faltantes = tramite.get("documentos_faltantes") or []
    avisos = tramite.get("avisos_pendientes") or []
    historial = tramite.get("historial") or []

    # Índice de avisos por tipo
    aviso1 = next((a for a in avisos if a.get("tipo") == "aviso_1"), None)
    aviso2 = next((a for a in avisos if a.get("tipo") == "aviso_2"), None)
    escalado = next((a for a in avisos if a.get("tipo") == "escalado"), None)

    ahora_iso = _ahora().isoformat()

    # ── Enviar aviso_1 si está preparado y no enviado vía SMTP ────────────────
    if aviso1 and not aviso1.get("enviado_smtp"):
        evidencia = tramite.get("documentos_evidencia") or []
        evidencia_detalle = tramite.get("documentos_evidencia_detalle") or {}
        asunto, html, texto = aviso_1(
            matricula=matricula,
            gestoria=gestoria,
            requisitos_faltantes=faltantes,
            requisitos_evidencia=evidencia,
            requisitos_evidencia_detalle=evidencia_detalle,
        )
        ok = await enviar_aviso(gestoria_email, asunto, html, texto)
        if ok:
            aviso1["enviado_smtp"] = True
            aviso1["enviado_smtp_at"] = ahora_iso
            historial.append({
                "momento": ahora_iso,
                "evento": f"Aviso 1 enviado a {gestoria_email}",
                "actor": "tyrion",
            })
            logger.info("Trámite %s: aviso_1 enviado a %s", tid, gestoria_email)
        return  # No continuar hasta que aviso_1 esté enviado

    # ── Aviso_2 (T+aviso2_min desde envío de aviso_1) ─────────────────────────
    aviso1_enviado_at = _parse_iso(aviso1.get("enviado_smtp_at") if aviso1 else None)
    if (
        aviso1_enviado_at
        and not aviso2
        and _minutos_desde(aviso1_enviado_at) >= cfg.escalado_aviso2_min
    ):
        asunto, html, texto = aviso_2(
            matricula=matricula,
            gestoria=gestoria,
            requisitos_faltantes=faltantes,
        )
        ok = await enviar_aviso(gestoria_email, asunto, html, texto)
        if ok:
            entry = {
                "tipo": "aviso_2",
                "enviado_at": ahora_iso,
                "enviado_smtp": True,
                "enviado_smtp_at": ahora_iso,
                "requisito": ", ".join(faltantes),
            }
            avisos.append(entry)
            historial.append({
                "momento": ahora_iso,
                "evento": f"Aviso 2 (recordatorio) enviado a {gestoria_email}",
                "actor": "tyrion",
            })
            logger.info("Trámite %s: aviso_2 enviado a %s", tid, gestoria_email)
        return

    # ── Escalado admin (T+escalado_min desde envío de aviso_1) ───────────────
    if (
        aviso1_enviado_at
        and not escalado
        and _minutos_desde(aviso1_enviado_at) >= cfg.escalado_admin_min
        and cfg.email_administrativo
    ):
        asunto, html, texto = escalado_admin(
            matricula=matricula,
            gestoria=gestoria,
            tramite_id=tid,
            requisitos_faltantes=faltantes,
        )
        ok = await enviar_aviso(cfg.email_administrativo, asunto, html, texto)
        if ok:
            entry = {
                "tipo": "escalado",
                "enviado_at": ahora_iso,
                "enviado_smtp": True,
                "enviado_smtp_at": ahora_iso,
                "requisito": ", ".join(faltantes),
            }
            avisos.append(entry)
            historial.append({
                "momento": ahora_iso,
                "evento": f"Escalado enviado al administrativo ({cfg.email_administrativo})",
                "actor": "tyrion",
            })
            logger.info("Trámite %s: escalado enviado a admin", tid)

        # Telegram si configurado
        if cfg.telegram_bot_token and cfg.telegram_chat_id_admin:
            pendientes_str = ", ".join(faltantes) or "sin detalle"
            texto_tg = (
                f"⚠️ <b>Tyrion — Escalado</b>\n"
                f"Trámite {matricula} ({tipo}) · Gestoría {gestoria}\n"
                f"Pendiente: {pendientes_str}\n"
                f"Sin respuesta tras {cfg.escalado_admin_min} min."
            )
            await enviar_mensaje_telegram(cfg.telegram_chat_id_admin, texto_tg)


async def run_timer_worker(intervalo: int = 60) -> None:
    """Loop periódico. Revisa avisos pendientes y dispara SMTP + Telegram."""
    from app.core.config import get_settings
    from app.services import registro_tramites

    cfg = get_settings()
    logger.info("Worker timers arrancado (intervalo=%ds).", intervalo)

    while True:
        try:
            tramites = registro_tramites.listar_tramites()
            pendientes = [t for t in tramites if t.get("estado") == "pendiente_gestoria"]

            for tramite in pendientes:
                try:
                    await _procesar_tramite(tramite, cfg)
                except Exception:
                    logger.exception("Error procesando timers para trámite %s", tramite.get("id"))

        except asyncio.CancelledError:
            logger.info("Worker timers detenido.")
            break
        except Exception:
            logger.exception("Error en ciclo del worker timers — reintentando en %ds.", intervalo)

        await asyncio.sleep(intervalo)
