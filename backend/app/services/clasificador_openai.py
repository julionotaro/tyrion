"""
Clasificador documental con OpenAI (gpt-4o-mini).

Usa visión nativa para imágenes y PDFs convertidos.
Para PDFs: extrae texto con PyMuPDF (fitz) primero (más barato y exacto).
Si la extracción de texto falla o el PDF es imagen escaneada → fallback a visión.

Principio de costos: gpt-4o-mini es equivalente a Haiku en precio,
adecuado para clasificación masiva. Reservar gpt-4o para conflictos.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from app.core.config import get_settings
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import (
    TipoDocumento,
    RASGOS_DISTINTIVOS,
    CONFUSIONES_FRECUENTES,
)

logger = logging.getLogger(__name__)

MEDIA_TYPES_IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _construir_prompt_sistema() -> str:
    rasgos = "\n".join(
        f"- {tipo.value}: {desc}" for tipo, desc in RASGOS_DISTINTIVOS.items()
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
1. El tipo declarado es solo una pista, NO un dato confiable.
2. Si no estás seguro, baja la confianza. Confianza honesta de 0.5 > falso 0.9.
3. Extrae los datos clave visibles: matrícula, bastidor, titular/nombre, DNI, importe, fechas.
4. Si no encaja en ningún tipo, devuelve "desconocido" con baja confianza.

Responde ÚNICAMENTE con un objeto JSON, sin texto adicional ni markdown:
{{
  "tipo_detectado": "uno de: {tipos_validos}",
  "confianza_score": 0.0 a 1.0,
  "datos_extraidos": {{"matricula": "...", "titular": "...", ...}},
  "justificacion": "1-2 frases sobre qué viste para decidir"
}}"""


def _extraer_texto_pdf(ruta: str) -> str | None:
    """Extrae texto de un PDF con PyMuPDF (fitz). Devuelve None si falla o vacío.

    PyMuPDF es más robusto que pdfplumber en contenedores Linux: no arrastra
    dependencias nativas problemáticas (cryptography/cffi) y es más rápido.
    """
    try:
        import fitz  # PyMuPDF
    except BaseException:
        return None
    try:
        doc = fitz.open(ruta)
        try:
            partes = [doc[i].get_text() or "" for i in range(min(4, doc.page_count))]
        finally:
            doc.close()
        texto = "\n".join(partes).strip()
        return texto if len(texto) > 50 else None
    except Exception as exc:
        logger.debug("PyMuPDF falló en %s: %s", ruta, exc)
        return None


def _nivel_desde_score(score: float) -> str:
    s = get_settings()
    if score >= s.confianza_alta:
        return "ALTA"
    if score >= s.confianza_media:
        return "MEDIA"
    return "BAJA"


def _parsear_respuesta(texto: str, tipo_declarado: str | None) -> ResultadoClasificacion:
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
        texto = texto.strip()
    try:
        data = json.loads(texto)
    except json.JSONDecodeError:
        logger.warning("OpenAI clasificador: respuesta no-JSON: %s", texto[:200])
        return ResultadoClasificacion(
            tipo_detectado=TipoDocumento.DESCONOCIDO,
            confianza_score=0.0,
            confianza_nivel="BAJA",
            justificacion="No se pudo interpretar la respuesta del clasificador.",
        )

    tipo_raw = str(data.get("tipo_detectado", "desconocido")).lower()
    try:
        tipo = TipoDocumento(tipo_raw)
    except ValueError:
        tipo = TipoDocumento.DESCONOCIDO

    score = float(data.get("confianza_score", 0.0))
    score = max(0.0, min(1.0, score))

    discrepancia = False
    if tipo_declarado:
        try:
            discrepancia = TipoDocumento(tipo_declarado.lower()) != tipo
        except ValueError:
            pass

    return ResultadoClasificacion(
        tipo_detectado=tipo,
        confianza_score=score,
        confianza_nivel=_nivel_desde_score(score),
        datos_extraidos=data.get("datos_extraidos", {}) or {},
        justificacion=str(data.get("justificacion", "")),
        discrepancia_con_declarado=discrepancia,
    )


class ClasificadorOpenAI:
    """Clasificador usando OpenAI gpt-4o-mini con visión.

    PDFs: extrae texto con pdfplumber primero (más rápido y barato).
    Si falla la extracción → envía imagen en base64 (visión).
    Imágenes: siempre visión.
    """

    def __init__(self, client=None):
        settings = get_settings()
        if client is not None:
            self._client = client
        else:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.clasificador_openai_model

    async def clasificar(
        self,
        ruta_archivo: str,
        tipo_declarado: str | None = None,
    ) -> ResultadoClasificacion:
        ext = Path(ruta_archivo).suffix.lower()
        sistema = _construir_prompt_sistema()
        hint = (
            f"\n\nEl remitente lo declaró como '{tipo_declarado}', "
            "pero verifica por ti mismo: puede estar equivocado."
            if tipo_declarado else ""
        )

        if ext == ".pdf":
            texto = _extraer_texto_pdf(ruta_archivo)
            if texto:
                # Ruta barata: texto puro
                respuesta = await self._cliente_texto(sistema, texto + hint)
                resultado = _parsear_respuesta(respuesta, tipo_declarado)
                logger.info(
                    "Clasificador OpenAI (texto) procesó %s → %s (confianza %.2f)",
                    Path(ruta_archivo).name, resultado.tipo_detectado.value,
                    resultado.confianza_score,
                )
                return resultado
            # Fallback: PDF como imagen (escaneado)
            return await self._clasificar_vision(ruta_archivo, "application/pdf", tipo_declarado)

        if ext in MEDIA_TYPES_IMG:
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif",
            }[ext]
            return await self._clasificar_vision(ruta_archivo, mime, tipo_declarado)

        raise ValueError(f"Tipo de archivo no soportado: {ext}")

    async def _cliente_texto(self, sistema: str, prompt: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0,
        )
        return resp.choices[0].message.content or ""

    async def _clasificar_vision(
        self, ruta: str, mime: str, tipo_declarado: str | None
    ) -> ResultadoClasificacion:
        hint = (
            f"\n\nEl remitente lo declaró como '{tipo_declarado}', "
            "pero verifica por ti mismo."
            if tipo_declarado else ""
        )
        data = Path(ruta).read_bytes()
        b64 = base64.standard_b64encode(data).decode()
        url = f"data:{mime};base64,{b64}"

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _construir_prompt_sistema()},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": f"Clasifica este documento.{hint}"},
                ]},
            ],
            max_tokens=512,
            temperature=0,
        )
        texto = resp.choices[0].message.content or ""
        resultado = _parsear_respuesta(texto, tipo_declarado)
        logger.info(
            "Clasificador OpenAI (visión) procesó %s → %s (confianza %.2f)",
            Path(ruta).name, resultado.tipo_detectado.value, resultado.confianza_score,
        )
        return resultado
