"""Agente conversacional de Tyrion para Telegram — motor GPT-4o-mini."""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_BASE = """Eres el asistente de Tyrion, el sistema de gestión documental del Colegio de Gestores de Pontevedra.
Eres cordial, profesional y conciso. Ayudas con consultas sobre trámites de vehículos.
No inventes información — solo informa lo que está en los datos reales del sistema.
Si no tienes información sobre algo, dilo claramente.
Nunca discutas temas ajenos a los trámites del Colegio.

Si el usuario pide subir documentos o ver el PDF de un documento, responde amablemente \
que eso no es posible por este canal y que debe enviar los documentos por email.

Usuario actual: {rol} — {identificador}
{contexto_tramites}"""


def _resumir_tramite(t: dict) -> str:
    mat = t.get("matricula") or t.get("id", "?")
    estado = t.get("estado", "?")
    faltantes = t.get("documentos_faltantes") or []
    falt_str = f", faltan: {', '.join(faltantes)}" if faltantes else ""
    return f"  • {mat} — {estado}{falt_str}"


def _contexto_admin() -> str:
    from app.services import registro_tramites
    from app.api.datos_prueba import TRAMITES_PRUEBA
    from app.core.config import get_settings

    cfg = get_settings()
    tramites = registro_tramites.listar_tramites()
    if cfg.use_datos_prueba:
        tramites = list(TRAMITES_PRUEBA) + tramites

    total = len(tramites)
    por_estado: dict[str, int] = {}
    alertas = []
    for t in tramites:
        e = t.get("estado", "desconocido")
        por_estado[e] = por_estado.get(e, 0) + 1
        if t.get("alerta"):
            alertas.append(t)

    resumen = f"Total trámites: {total}\n"
    resumen += "Por estado: " + ", ".join(f"{e}={n}" for e, n in por_estado.items()) + "\n"
    if alertas:
        resumen += f"Con alerta ({len(alertas)}):\n"
        for t in alertas[:5]:
            resumen += _resumir_tramite(t) + "\n"
        if len(alertas) > 5:
            resumen += f"  ... y {len(alertas) - 5} más.\n"
    resumen += "\nTodos los trámites:\n"
    for t in tramites[:20]:
        resumen += _resumir_tramite(t) + "\n"
    return resumen


def _contexto_gestoria(email_gestoria: str) -> str:
    from app.services import registro_tramites
    from app.api.datos_prueba import TRAMITES_PRUEBA
    from app.core.config import get_settings

    cfg = get_settings()
    tramites = registro_tramites.listar_tramites()
    if cfg.use_datos_prueba:
        tramites = list(TRAMITES_PRUEBA) + tramites

    propios = [
        t for t in tramites
        if t.get("gestoria_email", "").lower() == email_gestoria.lower()
    ]
    if not propios:
        return "Esta gestoría no tiene trámites registrados actualmente."

    lineas = [f"Trámites de esta gestoría ({len(propios)}):"]
    for t in propios:
        lineas.append(_resumir_tramite(t))
    return "\n".join(lineas)


async def procesar_mensaje(
    chat_id: str,
    texto: str,
    usuario: dict | None,
) -> str:
    """Interpreta el mensaje con GPT-4o-mini y devuelve la respuesta."""
    from app.core.config import get_settings
    from openai import AsyncOpenAI

    cfg = get_settings()
    if not cfg.openai_api_key:
        return "El agente no está disponible en este momento (sin clave API configurada)."

    if usuario is None:
        return (
            "No tengo tu cuenta registrada. "
            "Por favor, contacta con la administración del Colegio para que te den acceso."
        )

    rol = usuario["rol"]
    identificador = usuario.get("nombre") or usuario.get("email") or chat_id

    if rol == "admin":
        contexto_tramites = "DATOS DEL SISTEMA (admin):\n" + _contexto_admin()
    else:
        email = usuario.get("email", "")
        contexto_tramites = "DATOS DE TU GESTORÍA:\n" + _contexto_gestoria(email)

    system_prompt = _SYSTEM_BASE.format(
        rol=rol,
        identificador=identificador,
        contexto_tramites=contexto_tramites,
    )

    try:
        client = AsyncOpenAI(api_key=cfg.openai_api_key)
        response = await client.chat.completions.create(
            model=cfg.clasificador_openai_model,  # gpt-4o-mini
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": texto},
            ],
            max_tokens=500,
            temperature=0.4,
        )
        return response.choices[0].message.content or "Sin respuesta."
    except Exception as exc:
        logger.error("Error en agente Telegram: %s", exc)
        return "Lo siento, no puedo responder en este momento. Intenta más tarde."


async def run_telegram_polling(intervalo: int = 3) -> None:
    """Loop de polling Telegram. Alternativa al webhook para servidores HTTP."""
    from app.core.config import get_settings
    from app.services.telegram_auth import identificar_usuario
    from app.services.telegram_sender import enviar_mensaje_telegram

    s = get_settings()
    if not s.telegram_bot_token:
        logger.info("Telegram polling desactivado (sin token).")
        return

    base_url = f"https://api.telegram.org/bot{s.telegram_bot_token}"
    offset = 0
    logger.info("Telegram polling arrancado (intervalo=%ds).", intervalo)

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 20, "limit": 10},
                )
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        chat_id = str(
                            update.get("message", {}).get("chat", {}).get("id", "")
                        )
                        texto = update.get("message", {}).get("text", "")
                        if chat_id and texto:
                            usuario = identificar_usuario(chat_id)
                            if usuario is None:
                                respuesta = (
                                    "Hola 👋 No tengo tu cuenta registrada en el sistema "
                                    "del Colegio de Gestores. Contactá con la administración "
                                    "para que te den acceso."
                                )
                            else:
                                respuesta = await procesar_mensaje(chat_id, texto, usuario)
                            await enviar_mensaje_telegram(chat_id, respuesta)
            except asyncio.CancelledError:
                logger.info("Telegram polling detenido.")
                break
            except Exception:
                logger.exception("Error en polling Telegram — reintentando.")
                await asyncio.sleep(intervalo)
                continue

            await asyncio.sleep(intervalo)
