"""
Tests específicos de la lógica PDF → texto/visión del ClasificadorOpenAI.

Regla crítica: NUNCA se manda un PDF directamente a la API de visión.
El flujo estricto es:
  PDF con texto   → OpenAI chat (texto puro, sin visión)
  PDF sin texto   → fitz convierte a PNG → OpenAI visión con image/png
  Imagen JPG/PNG  → OpenAI visión directamente
"""
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.clasificador_openai import ClasificadorOpenAI
from app.services.catalogo_documental import TipoDocumento

PDF_MINIMO = b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj"
PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPG_FAKE = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _respuesta(tipo: str, score: float = 0.92) -> SimpleNamespace:
    texto = json.dumps({
        "tipo_detectado": tipo,
        "confianza_score": score,
        "datos_extraidos": {},
        "justificacion": "Test",
    })
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


def _cliente(tipo: str, score: float = 0.92):
    c = MagicMock()
    c.chat.completions.create = AsyncMock(return_value=_respuesta(tipo, score))
    return c


def _mime_usado(cliente) -> str | None:
    """Devuelve el MIME type de la imagen mandada a visión, o None si se usó chat de texto."""
    call_kwargs = cliente.chat.completions.create.call_args.kwargs
    msgs = call_kwargs.get("messages", [])
    for m in msgs:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        return url.split(";")[0].replace("data:", "")
    return None  # fue llamada de texto puro


@pytest.mark.asyncio
async def test_pdf_con_texto_usa_chat_no_vision(tmp_path):
    """PDF con texto extraíble → llama a chat (texto puro), NO manda imagen."""
    pdf = tmp_path / "transferencia.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente("cti", 0.95)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf",
               return_value="CERTIFICADO DE TRANSFERENCIA INDIVIDUAL matrícula 1234ABC"):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.CTI
    mime = _mime_usado(cliente)
    assert mime is None, f"PDF con texto NO debe usar visión, pero usó MIME: {mime}"


@pytest.mark.asyncio
async def test_pdf_sin_texto_convierte_a_png_no_pdf(tmp_path):
    """PDF sin texto → fitz lo convierte a PNG → visión recibe image/png, NUNCA application/pdf."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente("modelo_620", 0.88)
    clf = ClasificadorOpenAI(client=cliente)

    with (
        patch("app.services.clasificador_openai._extraer_texto_pdf", return_value=None),
        patch("app.services.clasificador_openai._pdf_paginas_png", return_value=[PNG_FAKE]),
    ):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.MODELO_620
    mime = _mime_usado(cliente)
    assert mime == "image/png", f"PDF sin texto debe mandar image/png, recibió: {mime}"
    assert mime != "application/pdf", "NUNCA se debe mandar application/pdf a visión"


@pytest.mark.asyncio
async def test_imagen_jpg_usa_vision_directamente(tmp_path):
    """Imagen JPG → llama a visión con image/jpeg directamente."""
    img = tmp_path / "doc.jpg"
    img.write_bytes(JPG_FAKE)

    cliente = _cliente("dni", 0.96)
    clf = ClasificadorOpenAI(client=cliente)
    resultado = await clf.clasificar(str(img))

    assert resultado.tipo_detectado == TipoDocumento.DNI
    mime = _mime_usado(cliente)
    assert mime == "image/jpeg", f"JPG debe mandar image/jpeg, recibió: {mime}"
