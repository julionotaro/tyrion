Contexto: Repo julionotaro/tyrion, rama main. Lee CLAUDE.md.
Mejora del agente conversacional de Telegram: respuestas con datos reales del
sistema en vez de derivar al email para consultas de estado.

PROBLEMA QUE RESUELVE
El agente responde "dirígete al email" para preguntas de estado y documentación
faltante que debería resolver con los datos reales que ya tiene en contexto. El
filtrado por gestoría ya es correcto — el trabajo es calidad de respuesta.

CAMBIO 1 — System prompt con instrucciones explícitas
En backend/app/services/telegram_agent.py, reemplazar _SYSTEM_BASE con:

_SYSTEM_BASE = """Eres el asistente de Tyrion, el sistema de gestión documental
del Colegio de Gestores de Pontevedra. Eres cordial, profesional y conciso.

REGLAS ESTRICTAS:
- Responde SIEMPRE con datos reales del sistema — nunca inventes.
- Para preguntas sobre estado o documentación de un trámite: usa los datos del
  contexto (documentos_faltantes, verificaciones, estado). Responde con detalle
  concreto: matrícula, estado actual, qué falta.
- Para preguntas sobre "mis trámites" o resumen: da el número de pendientes y
  lista las matrículas con estado.
- Para preguntas sobre un trámite específico (matrícula o bastidor): busca ese
  trámite y responde con estado + faltantes + si hay aviso pendiente.
- SOLO deriva al email para: subir documentos, adjuntar PDFs, enviar
  documentación nueva. Para consultas de estado/faltantes NO derives al email.
- Si no tienes información de algo, dilo claramente y sin inventar.
- No discutas temas ajenos a los trámites del Colegio.

Usuario actual: {rol} — {identificador}
{contexto_tramites}"""

CAMBIO 2 — _resumir_tramite con gestoría y faltantes
def _resumir_tramite(t: dict) -> str:
    mat = t.get("matricula") or t.get("id", "?")
    estado = t.get("estado", "?")
    gest = t.get("gestoria") or t.get("gestoria_email", "")
    faltantes = t.get("documentos_faltantes") or []
    falt_str = f" | faltan: {', '.join(faltantes)}" if faltantes else ""
    gest_str = f" [{gest}]" if gest else ""
    return f"  • {mat}{gest_str} — {estado}{falt_str}"

CAMBIO 3 — _contexto_gestoria con verificaciones por trámite
En el bucle que construye lineas, después de _resumir_tramite(t):
    verifs = t.get("verificaciones") or []
    for v in verifs:
        if not v.get("ok"):
            aviso = v.get("aviso") or v.get("descripcion", "")
            lineas.append(f"      ↳ {v['campo']}: {aviso[:120]}")

CAMBIO 4 — max_tokens
En la llamada al modelo, subir max_tokens de 500 a 800.

Tests
- Import limpio: cd backend && python -c "from app.services.telegram_agent import procesar_mensaje; print('OK')"
- Suite completa: cd backend && python -m pytest tests/ -x -q (todo verde).

Commit: feat: telegram agente con respuestas detalladas (Encargo 2)
Verificación manual: desde Telegram, "¿qué falta en el trámite 5042HZM?" → el
agente responde con los faltantes reales en vez de derivar al email.
