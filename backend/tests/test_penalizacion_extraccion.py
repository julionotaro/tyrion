"""
Tests: penalización de confianza cuando la extracción está incompleta.

Aplica a ambos clasificadores (ClasificadorOpenAI y ClasificadorDocumental Anthropic)
via sus respectivas funciones _parsear_respuesta.
"""
import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.clasificador_openai import ClasificadorOpenAI, _parsear_respuesta as _parsear_openai
from app.services.catalogo_documental import TipoDocumento


def _respuesta_openai(tipo: str, score: float, datos: dict) -> SimpleNamespace:
    texto = json.dumps({
        "tipo_detectado": tipo,
        "confianza_score": score,
        "datos_extraidos": datos,
        "justificacion": "Test",
    })
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


def test_openai_con_todos_los_campos_confianza_intacta():
    """CTI con todos los campos → confianza original sin penalizar."""
    datos = {"matricula": "1234ABC", "titular": "Juan García", "bastidor": "WBA12345"}
    resultado = _parsear_openai(json.dumps({
        "tipo_detectado": "cti",
        "confianza_score": 0.93,
        "datos_extraidos": datos,
        "justificacion": "Veo el CTI completo",
    }), tipo_declarado=None)
    assert resultado.confianza_score == 0.93
    assert resultado.requiere_validacion_humana is False
    assert resultado.campos_faltantes == []


def test_openai_datos_vacios_penaliza():
    """CTI sin datos extraídos → confianza ≤ 0.5, BAJA, requiere_validacion_humana=True."""
    resultado = _parsear_openai(json.dumps({
        "tipo_detectado": "cti",
        "confianza_score": 0.92,
        "datos_extraidos": {},
        "justificacion": "Veo algo",
    }), tipo_declarado=None)
    assert resultado.confianza_score <= 0.5
    assert resultado.confianza_nivel == "BAJA"
    assert resultado.requiere_validacion_humana is True
    assert "matricula" in resultado.campos_faltantes
    assert "titular" in resultado.campos_faltantes
    assert "bastidor" in resultado.campos_faltantes
    assert "Extracción incompleta" in resultado.justificacion


def test_openai_datos_parciales_penaliza():
    """CTI con solo matrícula → confianza penalizada."""
    resultado = _parsear_openai(json.dumps({
        "tipo_detectado": "cti",
        "confianza_score": 0.88,
        "datos_extraidos": {"matricula": "1234ABC"},
        "justificacion": "Parcial",
    }), tipo_declarado=None)
    assert resultado.confianza_score <= 0.5
    assert resultado.requiere_validacion_humana is True
    assert "titular" in resultado.campos_faltantes
    assert "bastidor" in resultado.campos_faltantes


def test_tipo_sin_campos_no_penaliza():
    """HOJA_CAJA (sin campos requeridos) no se penaliza aunque datos_extraidos sea {}."""
    resultado = _parsear_openai(json.dumps({
        "tipo_detectado": "hoja_caja",
        "confianza_score": 0.80,
        "datos_extraidos": {},
        "justificacion": "Es la hoja de caja",
    }), tipo_declarado=None)
    assert resultado.confianza_score == 0.80
    assert resultado.campos_faltantes == []
    assert resultado.requiere_validacion_humana is False


def test_nulos_explicitos_cuentan_como_faltantes():
    """Campos con None devueltos por el modelo se tratan como faltantes."""
    resultado = _parsear_openai(json.dumps({
        "tipo_detectado": "cti",
        "confianza_score": 0.90,
        "datos_extraidos": {"matricula": "1234ABC", "titular": None, "bastidor": None},
        "justificacion": "Test nulos",
    }), tipo_declarado=None)
    assert resultado.requiere_validacion_humana is True
    assert "titular" in resultado.campos_faltantes


@pytest.mark.asyncio
async def test_clasificador_openai_penaliza_en_classify(tmp_path):
    """Integración: ClasificadorOpenAI.clasificar() penaliza extracción incompleta."""
    PDF_MINIMO = b"%PDF-1.4"
    pdf = tmp_path / "cti.pdf"
    pdf.write_bytes(PDF_MINIMO)

    resp = _respuesta_openai("cti", 0.95, {"matricula": "1234ABC"})  # faltan titular y bastidor
    cliente = MagicMock()
    cliente.chat.completions.create = AsyncMock(return_value=resp)
    clf = ClasificadorOpenAI(client=cliente)

    with patch("app.services.clasificador_openai._extraer_texto_pdf",
               return_value="CERTIFICADO DE TRANSFERENCIA texto largo suficiente"):
        resultado = await clf.clasificar(str(pdf))

    assert resultado.confianza_score <= 0.5
    assert resultado.requiere_validacion_humana is True
    assert "titular" in resultado.campos_faltantes
