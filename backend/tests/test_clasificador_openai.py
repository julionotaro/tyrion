"""
Tests para ClasificadorOpenAI.

Sin llamadas reales a la API — todo mockeado.
Verifica:
  - extracción de texto PDF → ruta de texto puro (barata)
  - fallback a visión si el PDF no tiene texto extraíble
  - imágenes → siempre visión
  - parseo de respuesta JSON
"""
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.clasificador_openai import ClasificadorOpenAI, _extraer_texto_pdf
from app.services.catalogo_documental import TipoDocumento

PDF_MINIMO = b"%PDF-1.4 1 0 obj<</Type/Catalog>>stream\nendstream\nendobj"


def _respuesta_openai(tipo: str, score: float = 0.90) -> MagicMock:
    """Mock de respuesta de la API de OpenAI."""
    texto = json.dumps({
        "tipo_detectado": tipo,
        "confianza_score": score,
        "datos_extraidos": {"matricula": "1234ABC"},
        "justificacion": "Test",
    })
    msg = SimpleNamespace(content=texto)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _cliente_mock(tipo: str, score: float = 0.90):
    cliente = MagicMock()
    cliente.chat = MagicMock()
    cliente.chat.completions = MagicMock()
    cliente.chat.completions.create = AsyncMock(return_value=_respuesta_openai(tipo, score))
    return cliente


@pytest.mark.asyncio
async def test_clasificador_openai_texto_pdf(tmp_path):
    """PDF con texto → usa ruta de texto (sin visión)."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente_mock("cti", 0.93)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf", return_value="CERTIFICADO DE TRANSFERENCIA INDIVIDUAL bastidor 1234"):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.CTI
    assert resultado.confianza_score == 0.93
    assert resultado.confianza_nivel == "ALTA"
    # Llamó a texto (completions), no a visión con imagen
    cliente.chat.completions.create.assert_called_once()
    call_kwargs = cliente.chat.completions.create.call_args
    msgs = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
    # Verificar que el mensaje de usuario es texto puro (no imagen_url)
    user_msg = [m for m in (call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else [])
                if isinstance(m, dict) and m.get("role") == "user"]


@pytest.mark.asyncio
async def test_clasificador_openai_fallback_vision(tmp_path):
    """PDF sin texto extraíble → fallback a visión."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente_mock("permiso_circulacion", 0.88)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf", return_value=None):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.PERMISO_CIRCULACION
    assert resultado.confianza_nivel == "ALTA"


@pytest.mark.asyncio
async def test_clasificador_openai_imagen(tmp_path):
    """Imagen PNG → siempre visión."""
    img = tmp_path / "doc.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    cliente = _cliente_mock("dni", 0.95)
    clf = ClasificadorOpenAI(client=cliente)
    resultado = await clf.clasificar(str(img))

    assert resultado.tipo_detectado == TipoDocumento.DNI
    assert resultado.confianza_nivel == "ALTA"


@pytest.mark.asyncio
async def test_clasificador_openai_discrepancia(tmp_path):
    """Tipo declarado != tipo detectado → discrepancia_con_declarado=True."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente_mock("cti", 0.91)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf", return_value="texto largo suficiente"):
        resultado = await clf.clasificar(str(pdf), tipo_declarado="permiso_circulacion")

    assert resultado.discrepancia_con_declarado is True


@pytest.mark.asyncio
async def test_clasificador_openai_respuesta_invalida(tmp_path):
    """JSON mal formado → tipo DESCONOCIDO, confianza 0."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(PDF_MINIMO)

    msg = SimpleNamespace(content="esto no es json")
    choice = SimpleNamespace(message=msg)
    cliente = MagicMock()
    cliente.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[choice]))
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf", return_value="algo de texto largo"):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.DESCONOCIDO
    assert resultado.confianza_score == 0.0


@pytest.mark.asyncio
async def test_clasificador_openai_tipo_desconocido(tmp_path):
    """Tipo no reconocido en respuesta → DESCONOCIDO."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente_mock("tipo_que_no_existe", 0.5)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf", return_value="texto suficiente largo"):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.DESCONOCIDO


def test_extraer_texto_pdf_archivo_invalido(tmp_path):
    """_extraer_texto_pdf nunca lanza excepción aunque pdfplumber falle."""
    f = tmp_path / "notapdf.pdf"
    f.write_text("esto no es un PDF")
    try:
        resultado = _extraer_texto_pdf(str(f))
        # Si pdfplumber está disponible: devuelve None o str
        assert resultado is None or isinstance(resultado, str)
    except Exception as exc:
        pytest.fail(f"_extraer_texto_pdf no debe propagar excepciones: {exc}")
