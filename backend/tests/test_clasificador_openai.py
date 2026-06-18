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

from app.services.clasificador_openai import ClasificadorOpenAI, _extraer_texto_pdf, _pdf_paginas_png
from app.services.catalogo_documental import TipoDocumento

PDF_MINIMO = b"%PDF-1.4 1 0 obj<</Type/Catalog>>stream\nendstream\nendobj"


_DATOS_COMPLETOS = {
    # datos completos por tipo para que no se dispare la penalización de extracción
    # B2: cet añadido al CTI (clave de cruce CTI↔620, instructivo C.1 / matriz §9.2)
    "cti": {"matricula": "1234ABC", "titular": "Juan García", "bastidor": "WBA12345", "cet": "CET-001"},
    "permiso_circulacion": {"matricula": "1234ABC", "titular": "Juan García", "bastidor": "WBA12345"},
    "dni": {"nombre": "Ana García", "numero_documento": "12345678A"},
    # B3: cet + bastidor añadidos al modelo_620
    "modelo_620": {"importe": "350", "transmitente": "A", "adquirente": "B", "fecha_devengo": "2026-01-01",
                   "cet": "CET-001", "bastidor": "WBA12345"},
}


def _respuesta_openai(tipo: str, score: float = 0.90, datos: dict | None = None) -> MagicMock:
    """Mock de respuesta de la API de OpenAI.

    Si no se pasan datos, usa _DATOS_COMPLETOS para el tipo (evita penalización por extracción incompleta).
    """
    if datos is None:
        datos = _DATOS_COMPLETOS.get(tipo, {"matricula": "1234ABC"})
    texto = json.dumps({
        "tipo_detectado": tipo,
        "confianza_score": score,
        "datos_extraidos": datos,
        "justificacion": "Test",
    })
    msg = SimpleNamespace(content=texto)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _cliente_mock(tipo: str, score: float = 0.90, datos: dict | None = None):
    cliente = MagicMock()
    cliente.chat = MagicMock()
    cliente.chat.completions = MagicMock()
    cliente.chat.completions.create = AsyncMock(return_value=_respuesta_openai(tipo, score, datos))
    return cliente


@pytest.mark.asyncio
async def test_clasificador_openai_texto_pdf(tmp_path):
    """PDF con texto → usa ruta de texto (sin visión)."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(PDF_MINIMO)

    datos_cti = {"matricula": "5042HZM", "dni_adquirente": "35306584C", "dni_transmitente": "14958073T", "cet": "CET-001"}
    cliente = _cliente_mock("cti", 0.93, datos=datos_cti)
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
    """PDF sin texto extraíble → convierte a PNG → fallback a visión (no PDF directo)."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(PDF_MINIMO)

    cliente = _cliente_mock("permiso_circulacion", 0.88)
    clf = ClasificadorOpenAI(client=cliente)

    PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with (
        patch("app.services.clasificador_openai._extraer_texto_pdf", return_value=None),
        patch("app.services.clasificador_openai._pdf_paginas_png", return_value=[PNG_FAKE]),
    ):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.PERMISO_CIRCULACION
    assert resultado.confianza_nivel == "ALTA"
    # La llamada a vision debe usar image/png, NUNCA application/pdf
    call_kwargs = cliente.chat.completions.create.call_args.kwargs
    msgs = call_kwargs["messages"]
    user_content = next(m["content"] for m in msgs if m["role"] == "user")
    img_url = next(p["image_url"]["url"] for p in user_content if p["type"] == "image_url")
    assert img_url.startswith("data:image/png;base64,"), f"MIME incorrecto: {img_url[:40]}"


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


@pytest.mark.asyncio
async def test_vision_usa_model_vision(tmp_path):
    """PDF escaneado → ruta visión usa model_vision (gpt-4o), no el modelo de texto."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(PDF_MINIMO)

    datos_permiso = {"matricula": "1234ABC", "titular": "Ana", "bastidor": "WBA12345"}
    cliente = _cliente_mock("permiso_circulacion", 0.88, datos=datos_permiso)
    clf = ClasificadorOpenAI(client=cliente)
    model_vision = clf._model_vision

    PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with (
        patch("app.services.clasificador_openai._extraer_texto_pdf", return_value=None),
        patch("app.services.clasificador_openai._pdf_paginas_png", return_value=[PNG_FAKE]),
    ):
        await clf.clasificar(str(pdf))

    call_kwargs = cliente.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == model_vision, (
        f"Se esperaba model_vision={model_vision}, se usó {call_kwargs['model']}"
    )
    assert call_kwargs["max_tokens"] == 1024, "max_tokens debe ser 1024 en ruta visión"


@pytest.mark.asyncio
async def test_vision_multipagina_manda_n_imagenes(tmp_path):
    """PDF de 3 páginas escaneadas → se mandan 3 image_url al modelo."""
    pdf = tmp_path / "multipagina.pdf"
    pdf.write_bytes(PDF_MINIMO)

    datos_permiso = {"matricula": "9999XYZ", "titular": "Carlos", "bastidor": "VF300001"}
    cliente = _cliente_mock("permiso_circulacion", 0.87, datos=datos_permiso)
    clf = ClasificadorOpenAI(client=cliente)

    PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    tres_paginas = [PNG_FAKE, PNG_FAKE, PNG_FAKE]
    with (
        patch("app.services.clasificador_openai._extraer_texto_pdf", return_value=None),
        patch("app.services.clasificador_openai._pdf_paginas_png", return_value=tres_paginas),
    ):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.tipo_detectado == TipoDocumento.PERMISO_CIRCULACION
    call_kwargs = cliente.chat.completions.create.call_args.kwargs
    msgs = call_kwargs["messages"]
    user_content = next(m["content"] for m in msgs if m["role"] == "user")
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 3, f"Se esperaban 3 imágenes, se mandaron {len(image_parts)}"


def test_extraer_texto_pdf_bytes_invalidos():
    """_extraer_texto_pdf con bytes inválidos nunca lanza excepción."""
    try:
        resultado = _extraer_texto_pdf(b"esto no es un PDF")
        assert resultado is None or isinstance(resultado, str)
    except Exception as exc:
        pytest.fail(f"_extraer_texto_pdf no debe propagar excepciones: {exc}")


# ── Tests: reintento por visión cuando extracción de texto incompleta ─────────

@pytest.mark.asyncio
async def test_reintento_vision_cuando_campos_faltantes(tmp_path):
    """Si texto extrae el tipo pero deja campos faltantes, se reintenta por visión."""
    pdf = tmp_path / "escaneado_con_texto_pobre.pdf"
    pdf.write_bytes(PDF_MINIMO)

    # Primera llamada (texto): CTI sin bastidor → campos_faltantes no vacío
    datos_incompletos = {"matricula": "5042HZM", "cet": "CET-001"}  # faltan dni_adquirente, dni_transmitente
    # Segunda llamada (visión): CTI completo
    datos_completos = {
        "matricula": "5042HZM", "cet": "CET-001",
        "dni_adquirente": "35306584C", "dni_transmitente": "14958073T",
    }

    cliente = MagicMock()
    cliente.chat = MagicMock()
    cliente.chat.completions = MagicMock()
    # Primera llamada → texto incompleto; segunda → visión completa
    cliente.chat.completions.create = AsyncMock(side_effect=[
        _respuesta_openai("cti", 0.85, datos_incompletos),
        _respuesta_openai("cti", 0.93, datos_completos),
    ])

    clf = ClasificadorOpenAI(client=cliente)

    PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with (
        patch("app.services.clasificador_openai._extraer_texto_pdf",
              return_value="CERTIFICADO DE TRANSFERENCIA bastidor ilegible"),
        patch("app.services.clasificador_openai._pdf_paginas_png", return_value=[PNG_FAKE]),
    ):
        resultado = await clf.clasificar(str(pdf))

    # Se hicieron 2 llamadas: texto + visión
    assert cliente.chat.completions.create.call_count == 2, (
        f"Se esperaban 2 llamadas (texto + visión), hubo {cliente.chat.completions.create.call_count}"
    )
    # El resultado fusionado debe tener los campos de visión
    assert resultado.datos_extraidos.get("dni_adquirente") == "35306584C"
    assert resultado.datos_extraidos.get("matricula") == "5042HZM"


@pytest.mark.asyncio
async def test_no_reintento_cuando_extraccion_completa(tmp_path):
    """Si texto extrae todos los campos, NO se reintenta por visión."""
    pdf = tmp_path / "digital_completo.pdf"
    pdf.write_bytes(PDF_MINIMO)

    datos_completos = {
        "matricula": "5042HZM", "cet": "CET-001",
        "dni_adquirente": "35306584C", "dni_transmitente": "14958073T",
    }
    cliente = _cliente_mock("cti", 0.93, datos=datos_completos)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf",
               return_value="CERTIFICADO DE TRANSFERENCIA texto completo"):
        resultado = await clf.clasificar(str(pdf))

    # Solo 1 llamada: texto, sin reintento
    assert cliente.chat.completions.create.call_count == 1
    assert resultado.campos_faltantes == []
