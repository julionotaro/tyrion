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
    CAMPOS_REQUERIDOS,
    evaluar_completitud_extraccion,
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
    campos_por_tipo = "\n".join(
        f"  - {tipo.value}: {campos}"
        for tipo, campos in CAMPOS_REQUERIDOS.items()
        if campos  # omitir tipos sin campos (hoja_caja, desconocido, etc.)
    )
    return f"""Eres el clasificador documental de una gestoría de trámites de vehículos ante la DGT española.

Tu tarea tiene DOS partes igual de importantes: (1) identificar QUÉ ES el documento, y (2) EXTRAER con precisión los campos de datos. La extracción es tan importante como la clasificación.

TIPOS DE DOCUMENTO QUE RECONOCES:
{rasgos}

CONFUSIONES FRECUENTES (mucho cuidado con estas):
{confusiones}

CAMPOS A EXTRAER POR TIPO (devuelve null si no encuentras el campo — NO lo omitas):
{campos_por_tipo}

REGLAS CRÍTICAS:
1. El tipo declarado es solo una pista, NO un dato confiable.
2. Si no estás seguro, baja la confianza. Confianza honesta de 0.5 > falso 0.9.
3. Extrae EXACTAMENTE los campos listados para el tipo que detectes. Usa null para los que no aparezcan.
4. Si no encaja en ningún tipo, devuelve "desconocido" con baja confianza.
5. Para documentos escaneados o de baja calidad, esfuérzate en leer números de identificación (DNI/NIF, matrícula, bastidor/VIN). Si un carácter es ambiguo, da tu mejor lectura y refléjalo bajando ligeramente la confianza, pero NO dejes el campo vacío si el dato es visible.

Responde ÚNICAMENTE con un objeto JSON, sin texto adicional ni markdown:
{{
  "tipo_detectado": "uno de: {tipos_validos}",
  "confianza_score": 0.0 a 1.0,
  "datos_extraidos": {{"campo": "valor o null si no aparece", ...}},
  "justificacion": "1-2 frases sobre qué viste para decidir"
}}"""


def _extraer_texto_pdf(contenido: bytes) -> str | None:
    """Extrae texto de un PDF con PyMuPDF (fitz). Devuelve None si falla o vacío."""
    try:
        import fitz  # PyMuPDF
    except BaseException:
        return None
    try:
        doc = fitz.open(stream=contenido, filetype="pdf")
        try:
            partes = [doc[i].get_text() or "" for i in range(min(4, doc.page_count))]
        finally:
            doc.close()
        texto = "\n".join(partes).strip()
        return texto if len(texto) > 50 else None
    except Exception as exc:
        logger.debug("PyMuPDF extraer_texto falló: %s", exc)
        return None


def _pdf_paginas_png(contenido: bytes, max_paginas: int = 4) -> list[bytes]:
    """Convierte hasta max_paginas de un PDF a PNG via PyMuPDF a 200 DPI.

    Corrige rotación automáticamente: si page.rotation != 0 aplica la matriz
    inversa para entregar la imagen siempre derecha (importante para apaisados
    como el Anexo 650, donde el bastidor en horizontal es muy difícil de leer).

    Devuelve lista vacía si falla o fitz no está instalado.
    """
    try:
        import fitz  # PyMuPDF
    except BaseException:
        return []
    try:
        doc = fitz.open(stream=contenido, filetype="pdf")
        try:
            paginas = []
            for i in range(min(max_paginas, doc.page_count)):
                page = doc.load_page(i)
                rot = page.rotation
                # Matriz base a 200 DPI + corrección de rotación inversa si hay giro
                mat = fitz.Matrix(200 / 72, 200 / 72)
                if rot != 0:
                    mat = fitz.Matrix(200 / 72, 200 / 72).prerotate(-rot)
                pix = page.get_pixmap(matrix=mat)
                paginas.append(pix.tobytes("png"))
        finally:
            doc.close()
        return paginas
    except Exception as exc:
        logger.debug("PyMuPDF pdf→png falló: %s", exc)
        return []


def _fusionar_resultados(
    texto: ResultadoClasificacion,
    vision: ResultadoClasificacion,
) -> ResultadoClasificacion:
    """Fusiona dos clasificaciones: toma los campos que visión encontró y texto no.

    Solo se fusiona si ambas coinciden en tipo_detectado. Si difieren, se devuelve
    el de mayor confianza_score (sin penalización por campos faltantes aplicada).
    Los campos combinados se revalúan con evaluar_completitud_extraccion.
    """
    if texto.tipo_detectado != vision.tipo_detectado:
        return texto if texto.confianza_score >= vision.confianza_score else vision

    campos_combinados = dict(vision.datos_extraidos or {})
    campos_combinados.update(texto.datos_extraidos or {})  # texto tiene prioridad si ambos tienen el campo
    for k, v in (vision.datos_extraidos or {}).items():
        campos_combinados.setdefault(k, v)

    completo, faltantes = evaluar_completitud_extraccion(texto.tipo_detectado, campos_combinados)
    score_base = max(texto.confianza_score, vision.confianza_score)
    if not completo:
        score_base = min(score_base, 0.5)
    nivel = _nivel_desde_score_raw(score_base)

    justificacion = texto.justificacion
    if vision.datos_extraidos:
        nuevos = [k for k in vision.datos_extraidos if k not in (texto.datos_extraidos or {})]
        if nuevos:
            justificacion += f" | Visión completó: {nuevos}"

    return ResultadoClasificacion(
        tipo_detectado=texto.tipo_detectado,
        confianza_score=score_base,
        confianza_nivel=nivel,
        datos_extraidos=campos_combinados,
        justificacion=justificacion,
        discrepancia_con_declarado=texto.discrepancia_con_declarado,
        requiere_validacion_humana=(nivel == "BAJA"),
        campos_faltantes=faltantes,
    )


def _nivel_desde_score_raw(score: float) -> str:
    s = get_settings()
    if score >= s.confianza_alta:
        return "ALTA"
    if score >= s.confianza_media:
        return "MEDIA"
    return "BAJA"


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
            requiere_validacion_humana=True,
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

    datos_extraidos = data.get("datos_extraidos", {}) or {}
    # Filtrar nulos explícitos que el modelo devuelve cuando no encuentra el campo
    datos_extraidos = {k: v for k, v in datos_extraidos.items() if v is not None and v != ""}
    justificacion = str(data.get("justificacion", ""))

    completo, campos_faltantes = evaluar_completitud_extraccion(tipo, datos_extraidos)
    if not completo:
        score = min(score, 0.5)
        justificacion += f" | Extracción incompleta: faltan {campos_faltantes}"

    nivel = _nivel_desde_score(score)
    requiere_validacion = nivel == "BAJA"

    return ResultadoClasificacion(
        tipo_detectado=tipo,
        confianza_score=score,
        confianza_nivel=nivel,
        datos_extraidos=datos_extraidos,
        justificacion=justificacion,
        discrepancia_con_declarado=discrepancia,
        requiere_validacion_humana=requiere_validacion,
        campos_faltantes=campos_faltantes,
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
        self._model_vision = settings.clasificador_openai_model_vision

    async def clasificar(
        self,
        ruta_archivo: str,
        tipo_declarado: str | None = None,
    ) -> ResultadoClasificacion:
        ext = Path(ruta_archivo).suffix.lower()
        contenido = Path(ruta_archivo).read_bytes()
        sistema = _construir_prompt_sistema()
        hint = (
            f"\n\nEl remitente lo declaró como '{tipo_declarado}', "
            "pero verifica por ti mismo: puede estar equivocado."
            if tipo_declarado else ""
        )

        if ext == ".pdf":
            # 1a. Intentar extracción de texto
            texto_pdf = _extraer_texto_pdf(contenido)
            if texto_pdf:
                # Ruta barata: texto puro, sin visión
                respuesta = await self._cliente_texto(sistema, texto_pdf + hint)
                resultado_texto = _parsear_respuesta(respuesta, tipo_declarado)
                logger.info(
                    "Clasificador OpenAI (texto) procesó %s → %s (confianza %.2f)",
                    Path(ruta_archivo).name, resultado_texto.tipo_detectado.value,
                    resultado_texto.confianza_score,
                )
                # Reintento por visión si la extracción de texto quedó incompleta
                if resultado_texto.campos_faltantes:
                    paginas = _pdf_paginas_png(contenido)
                    if paginas:
                        logger.info(
                            "Reintento visión para %s: campos faltantes tras texto: %s",
                            Path(ruta_archivo).name, resultado_texto.campos_faltantes,
                        )
                        resultado_vision = await self._clasificar_vision_bytes(
                            paginas, "image/png", tipo_declarado, ruta_archivo,
                        )
                        return _fusionar_resultados(resultado_texto, resultado_vision)
                return resultado_texto
            # 1c. PDF escaneado: convertir todas las páginas (hasta 4) a PNG con 200 DPI
            paginas = _pdf_paginas_png(contenido)
            if paginas:
                return await self._clasificar_vision_bytes(
                    paginas, "image/png", tipo_declarado, ruta_archivo,
                )
            raise ValueError(
                f"No se pudo extraer texto ni convertir a imagen el PDF '{Path(ruta_archivo).name}'. "
                "Comprueba que PyMuPDF (fitz) está instalado."
            )

        if ext in MEDIA_TYPES_IMG:
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif",
            }[ext]
            return await self._clasificar_vision_bytes([contenido], mime, tipo_declarado, ruta_archivo)

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

    async def _clasificar_vision_bytes(
        self,
        imagenes: list[bytes],
        mime: str,
        tipo_declarado: str | None,
        ruta_original: str = "",
    ) -> ResultadoClasificacion:
        """Manda una o varias imágenes (PNG/JPG — NUNCA PDF) al modelo de visión.

        Usa self._model_vision (gpt-4o por defecto) para mejor OCR en escaneos.
        Manda todas las páginas como múltiples image_url en el mismo mensaje de usuario.
        """
        hint = (
            f"\n\nEl remitente lo declaró como '{tipo_declarado}', "
            "pero verifica por ti mismo."
            if tipo_declarado else ""
        )
        contenido_usuario: list[dict] = []
        for img_bytes in imagenes:
            b64 = base64.standard_b64encode(img_bytes).decode()
            url = f"data:{mime};base64,{b64}"
            contenido_usuario.append({"type": "image_url", "image_url": {"url": url}})
        paginas_str = f"{len(imagenes)} página(s)" if len(imagenes) > 1 else "este documento"
        contenido_usuario.append(
            {"type": "text", "text": f"Clasifica {paginas_str}.{hint}"}
        )

        resp = await self._client.chat.completions.create(
            model=self._model_vision,
            messages=[
                {"role": "system", "content": _construir_prompt_sistema()},
                {"role": "user", "content": contenido_usuario},
            ],
            max_tokens=1024,
            temperature=0,
        )
        texto = resp.choices[0].message.content or ""
        resultado = _parsear_respuesta(texto, tipo_declarado)
        nombre = Path(ruta_original).name if ruta_original else "imagen"
        logger.info(
            "Clasificador OpenAI (visión/%s, %d pág.) procesó %s → %s (confianza %.2f)",
            self._model_vision, len(imagenes), nombre,
            resultado.tipo_detectado.value, resultado.confianza_score,
        )
        return resultado
