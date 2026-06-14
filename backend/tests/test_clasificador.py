"""
Tests del clasificador documental.

Usan un cliente Claude mockeado: no hacen llamadas reales a la API ni
dependen de red. Verifican la lógica de parsing, normalización de tipos,
cálculo de niveles de confianza y detección de discrepancias — que es donde
viven los bugs reales.
"""
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento
from app.services.clasificador import ClasificadorDocumental, _nivel_desde_score


# ---------- helpers ----------

def _fake_message(texto: str):
    """Construye un objeto-respuesta con la forma que devuelve el SDK de Anthropic."""
    bloque = SimpleNamespace(type="text", text=texto)
    return SimpleNamespace(content=[bloque])


def _clasificador_con_respuesta(texto: str) -> ClasificadorDocumental:
    """Clasificador con un cliente mock que siempre devuelve `texto`."""
    client = SimpleNamespace()
    client.messages = SimpleNamespace(
        create=AsyncMock(return_value=_fake_message(texto))
    )
    return ClasificadorDocumental(client=client)


@pytest.fixture
def pdf_falso(tmp_path):
    """Crea un PDF mínimo en disco para que _leer_archivo_b64 no falle."""
    ruta = tmp_path / "doc.pdf"
    ruta.write_bytes(b"%PDF-1.4 fake content")
    return str(ruta)


# ---------- niveles de confianza ----------

@pytest.mark.parametrize("score,esperado", [
    (0.95, "ALTA"),
    (0.85, "ALTA"),
    (0.84, "MEDIA"),
    (0.60, "MEDIA"),
    (0.59, "BAJA"),
    (0.0, "BAJA"),
])
def test_nivel_desde_score(score, esperado):
    assert _nivel_desde_score(score) == esperado


# ---------- clasificación feliz ----------

@pytest.mark.asyncio
async def test_clasifica_permiso_con_confianza_alta(pdf_falso):
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "permiso_circulacion", "confianza_score": 0.95, '
        '"datos_extraidos": {"matricula": "1234ABC", "titular": "Juan Pérez"}, '
        '"justificacion": "Encabezado Permiso de Circulación visible."}'
    )
    res = await clf.clasificar(pdf_falso)

    assert isinstance(res, ResultadoClasificacion)
    assert res.tipo_detectado == TipoDocumento.PERMISO_CIRCULACION
    assert res.confianza_score == 0.95
    assert res.confianza_nivel == "ALTA"
    assert res.datos_extraidos["matricula"] == "1234ABC"
    assert not res.requiere_validacion_humana


# ---------- la regla de oro de la entrevista: dijeron Permiso, era 620 ----------

@pytest.mark.asyncio
async def test_detecta_discrepancia_con_tipo_declarado(pdf_falso):
    """El remitente dice 'permiso_circulacion' pero el documento es un 620."""
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "modelo_620", "confianza_score": 0.88, '
        '"datos_extraidos": {}, "justificacion": "Número 620 y casillas de liquidación."}'
    )
    res = await clf.clasificar(pdf_falso, tipo_declarado="permiso_circulacion")

    assert res.tipo_detectado == TipoDocumento.MODELO_620
    assert res.discrepancia_con_declarado is True


@pytest.mark.asyncio
async def test_sin_discrepancia_cuando_coinciden(pdf_falso):
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "dni", "confianza_score": 0.9, '
        '"datos_extraidos": {}, "justificacion": "DNI visible."}'
    )
    res = await clf.clasificar(pdf_falso, tipo_declarado="dni")
    assert res.discrepancia_con_declarado is False


# ---------- confianza baja activa revisión humana ----------

@pytest.mark.asyncio
async def test_confianza_baja_requiere_validacion(pdf_falso):
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "cti", "confianza_score": 0.45, '
        '"datos_extraidos": {}, "justificacion": "Imagen borrosa, no concluyente."}'
    )
    res = await clf.clasificar(pdf_falso)

    assert res.confianza_nivel == "BAJA"
    assert res.requiere_validacion_humana is True


# ---------- robustez del parsing ----------

@pytest.mark.asyncio
async def test_respuesta_con_fences_markdown(pdf_falso):
    """Claude a veces envuelve el JSON en ```json ... ```. Debe limpiarse."""
    clf = _clasificador_con_respuesta(
        '```json\n{"tipo_detectado": "dni", "confianza_score": 0.9, '
        '"datos_extraidos": {}, "justificacion": "ok"}\n```'
    )
    res = await clf.clasificar(pdf_falso)
    assert res.tipo_detectado == TipoDocumento.DNI


@pytest.mark.asyncio
async def test_respuesta_no_json_degrada_a_desconocido(pdf_falso):
    clf = _clasificador_con_respuesta("No puedo leer este documento, lo siento.")
    res = await clf.clasificar(pdf_falso)

    assert res.tipo_detectado == TipoDocumento.DESCONOCIDO
    assert res.confianza_score == 0.0
    assert res.requiere_validacion_humana is True


@pytest.mark.asyncio
async def test_tipo_invalido_degrada_a_desconocido(pdf_falso):
    """Si Claude inventa un tipo fuera del catálogo, se normaliza a desconocido."""
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "pasaporte_extraterrestre", "confianza_score": 0.7, '
        '"datos_extraidos": {}, "justificacion": "?"}'
    )
    res = await clf.clasificar(pdf_falso)
    assert res.tipo_detectado == TipoDocumento.DESCONOCIDO


@pytest.mark.asyncio
async def test_score_fuera_de_rango_se_clampa(pdf_falso):
    clf = _clasificador_con_respuesta(
        '{"tipo_detectado": "dni", "confianza_score": 1.7, '
        '"datos_extraidos": {}, "justificacion": "x"}'
    )
    res = await clf.clasificar(pdf_falso)
    assert res.confianza_score == 1.0


# ---------- validación de archivos ----------

@pytest.mark.asyncio
async def test_archivo_no_soportado_lanza_error(tmp_path):
    ruta = tmp_path / "doc.docx"
    ruta.write_bytes(b"contenido")
    clf = _clasificador_con_respuesta("{}")

    with pytest.raises(ValueError, match="no soportado"):
        await clf.clasificar(str(ruta))
