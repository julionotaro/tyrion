"""
Clasificador documental de Tyrion — PRIMER MÓDULO.

Identificado en la entrevista como el cuello de botella: el 80% del tiempo
administrativo se va en el cotejo documental. Este módulo automatiza el primer
paso de ese cotejo: identificar QUÉ es cada documento que llega.

Implementa la capa 3 del modelo de cuatro capas (documento DETECTADO).
NO decide validez — eso vive en el vínculo documento-trámite y depende del
checklist del tipo de trámite. Aquí solo se detecta el tipo con su confianza.

Principio de costos (presupuesto €150/mes, ~4-6k docs/mes):
  - Modelo económico (Haiku) para clasificación masiva.
  - El modelo premium (Opus) se reserva para conflictos y escalados, en otro módulo.

El clasificador es deliberadamente escéptico del tipo DECLARADO por el remitente:
la entrevista mostró que las gestorías dicen "Permiso" y envían un 620. El tipo
declarado es una pista, no un dato confiable.
"""
import base64
import json
import logging
from pathlib import Path

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import (
    TipoDocumento,
    RASGOS_DISTINTIVOS,
    CONFUSIONES_FRECUENTES,
)

logger = logging.getLogger(__name__)

# Tipos de archivo que Claude puede leer con visión nativa
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _construir_prompt_sistema() -> str:
    """Prompt de sistema con el catálogo documental del dominio."""
    rasgos = "\n".join(
        f"- {tipo.value}: {desc}"
        for tipo, desc in RASGOS_DISTINTIVOS.items()
    )
    confusiones = "\n".join(
        f"- Un '{tipo.value}' se confunde con: {', '.join(c.value for c in conf)}"
        for tipo, conf in CONFUSIONES_FRECUENTES.items()
    )
    tipos_validos = ", ".join(t.value for t in TipoDocumento)

    return f"""Eres el clasificador documental de una gestoría de trámites de vehículos ante la DGT española.

Tu tarea: identificar QUÉ ES un documento, con un nivel de confianza honesto.

TIPOS DE DOCUMENTO QUE RECONOCES:
{rasgos}

CONFUSIONES FRECUENTES (mucho cuidado con estas):
{confusiones}

REGLAS CRÍTICAS:
1. El tipo que el remitente DECLARA es solo una pista, NO un dato confiable. Las gestorías dicen "Permiso" y envían un Modelo 620. Clasifica por lo que VES en el documento, no por lo que digan.
2. Si no estás seguro, baja la confianza. Es mejor una confianza honesta de 0.5 que un 0.9 equivocado: la confianza baja activa revisión humana, un falso 0.9 deja pasar un error.
3. Extrae los datos clave que veas para el cotejo posterior: matrícula, bastidor, titular/nombre, DNI, importe, fechas. Solo lo que realmente aparezca.
4. Si el documento no encaja en ningún tipo conocido, devuelve "desconocido" con baja confianza.

Responde ÚNICAMENTE con un objeto JSON, sin texto adicional ni markdown:
{{
  "tipo_detectado": "uno de: {tipos_validos}",
  "confianza_score": 0.0 a 1.0,
  "datos_extraidos": {{"matricula": "...", "titular": "...", ...}},
  "justificacion": "1-2 frases sobre qué viste para decidir"
}}"""


def _nivel_desde_score(score: float) -> str:
    s = get_settings()
    if score >= s.confianza_alta:
        return "ALTA"
    if score >= s.confianza_media:
        return "MEDIA"
    return "BAJA"


def _leer_archivo_b64(ruta: str) -> tuple[str, str]:
    """Devuelve (media_type, contenido_base64). Lanza ValueError si no es soportado."""
    ext = Path(ruta).suffix.lower()
    if ext not in MEDIA_TYPES:
        raise ValueError(f"Tipo de archivo no soportado para visión: {ext}")
    data = Path(ruta).read_bytes()
    return MEDIA_TYPES[ext], base64.standard_b64encode(data).decode()


class ClasificadorMock:
    """Clasificador sin llamadas a API — para demo y tests sin ANTHROPIC_API_KEY."""

    async def clasificar(
        self,
        ruta_archivo: str | None = None,
        tipo_declarado: str | None = None,
        contenido: bytes | None = None,
    ) -> "ResultadoClasificacion":
        tipo = TipoDocumento.DESCONOCIDO
        if tipo_declarado:
            try:
                tipo = TipoDocumento(tipo_declarado.lower())
            except ValueError:
                pass
        return ResultadoClasificacion(
            tipo_detectado=tipo,
            confianza_score=0.75,
            confianza_nivel="MEDIA",
            justificacion="Clasificador mock (sin API key): tipo inferido del nombre declarado.",
        )


class ClasificadorDocumental:
    """Clasifica documentos usando la visión de Claude.

    Se inyecta el cliente para poder testear sin llamadas reales a la API.
    Si ANTHROPIC_API_KEY no está configurada, usa ClasificadorMock automáticamente.
    """

    def __init__(self, client=None):
        settings = get_settings()
        self._mock_clf = ClasificadorMock()

        if client is not None:
            # Cliente inyectado (tests)
            self._client = client
            self._mock = False
            self._openai = False
        elif settings.openai_api_key:
            # OpenAI tiene prioridad cuando ambas keys están configuradas
            logger.info("Clasificador: modo OpenAI (%s)", settings.clasificador_openai_model)
            from app.services.clasificador_openai import ClasificadorOpenAI
            self._openai_clf = ClasificadorOpenAI()
            self._client = None
            self._mock = False
            self._openai = True
        elif settings.anthropic_api_key:
            logger.info("Clasificador: modo Anthropic (%s)", settings.clasificador_model)
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self._mock = False
            self._openai = False
        else:
            logger.info("Clasificador: modo mock (sin API key)")
            self._client = None
            self._mock = True
            self._openai = False
        self._model = settings.clasificador_model

    async def clasificar(
        self,
        ruta_archivo: str,
        tipo_declarado: str | None = None,
    ) -> ResultadoClasificacion:
        """Clasifica un documento. Delega al mock o a OpenAI según configuración."""
        if self._mock:
            return await self._mock_clf.clasificar(
                ruta_archivo=ruta_archivo, tipo_declarado=tipo_declarado
            )
        if self._openai:
            return await self._openai_clf.clasificar(
                ruta_archivo=ruta_archivo, tipo_declarado=tipo_declarado
            )

        media_type, contenido_b64 = _leer_archivo_b64(ruta_archivo)

        bloque_doc = "document" if media_type == "application/pdf" else "image"
        user_text = "Clasifica este documento."
        if tipo_declarado:
            user_text += (
                f"\n\nEl remitente lo declaró como '{tipo_declarado}', "
                "pero verifica por ti mismo: puede estar equivocado."
            )

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_construir_prompt_sistema(),
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": bloque_doc,
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": contenido_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }],
        )

        return self._parsear_respuesta(message, tipo_declarado)

    def _parsear_respuesta(
        self, message, tipo_declarado: str | None
    ) -> ResultadoClasificacion:
        """Extrae y valida el JSON de la respuesta de Claude."""
        texto = "".join(
            b.text for b in message.content if getattr(b, "type", None) == "text"
        ).strip()

        # Robustez: limpiar posibles fences de markdown
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
            texto = texto.strip()

        try:
            data = json.loads(texto)
        except json.JSONDecodeError:
            logger.warning("Respuesta no-JSON del clasificador: %s", texto[:200])
            return ResultadoClasificacion(
                tipo_detectado=TipoDocumento.DESCONOCIDO,
                confianza_score=0.0,
                confianza_nivel="BAJA",
                justificacion="No se pudo interpretar la respuesta del clasificador.",
            )

        # Normalizar el tipo a un valor válido del enum
        tipo_raw = str(data.get("tipo_detectado", "desconocido")).lower()
        try:
            tipo = TipoDocumento(tipo_raw)
        except ValueError:
            tipo = TipoDocumento.DESCONOCIDO

        score = float(data.get("confianza_score", 0.0))
        score = max(0.0, min(1.0, score))  # clamp defensivo

        discrepancia = False
        if tipo_declarado:
            try:
                discrepancia = TipoDocumento(tipo_declarado.lower()) != tipo
            except ValueError:
                discrepancia = False

        return ResultadoClasificacion(
            tipo_detectado=tipo,
            confianza_score=score,
            confianza_nivel=_nivel_desde_score(score),
            datos_extraidos=data.get("datos_extraidos", {}) or {},
            justificacion=str(data.get("justificacion", "")),
            discrepancia_con_declarado=discrepancia,
        )
