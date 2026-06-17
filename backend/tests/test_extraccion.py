"""
QA sistémico de extracción por familia documental.

Por cada familia verifica:
  (a) datos completos → evaluar_completitud_extraccion devuelve True, sin penalización
  (b) datos vacíos   → evaluar_completitud_extraccion devuelve False, confianza penalizada
      (solo para tipos con campos requeridos)

Usa ResultadoClasificacion y _parsear_respuesta (OpenAI) con payloads sintéticos.
NO llama a ninguna API real.
"""
import json
import pytest
from app.services.catalogo_documental import TipoDocumento, evaluar_completitud_extraccion
from app.services.clasificador_openai import _parsear_respuesta


def _payload(tipo: str, score: float, datos: dict) -> str:
    return json.dumps({
        "tipo_detectado": tipo,
        "confianza_score": score,
        "datos_extraidos": datos,
        "justificacion": "Test sintético",
    })


# ── Fixtures de datos completos por familia ────────────────────────────────────

DATOS_COMPLETOS = {
    TipoDocumento.CTI: {
        "matricula": "1234 ABC", "titular": "Luis Fernández", "bastidor": "WVW12345",
    },
    TipoDocumento.MODELO_620: {
        "importe": "487.50", "transmitente": "Pedro López",
        "adquirente": "María García", "fecha_devengo": "2026-06-01",
    },
    TipoDocumento.ANEXO_650: {
        "bastidor": "WVW12345", "valor_vehiculo": "12000",
    },
    TipoDocumento.DNI: {
        "nombre": "Ana Martínez", "numero_documento": "12345678Z",
    },
    TipoDocumento.FICHA_TECNICA: {
        "marca": "Volkswagen", "modelo": "Golf", "bastidor": "WVW12345",
    },
}


# ── CTI ────────────────────────────────────────────────────────────────────────

class TestCTI:
    def test_completo_no_penaliza(self):
        resultado = _parsear_respuesta(_payload("cti", 0.95, DATOS_COMPLETOS[TipoDocumento.CTI]), None)
        assert resultado.confianza_score == 0.95
        assert resultado.requiere_validacion_humana is False
        assert resultado.campos_faltantes == []

    def test_incompleto_penaliza(self):
        resultado = _parsear_respuesta(_payload("cti", 0.95, {}), None)
        assert resultado.confianza_score <= 0.5
        assert resultado.requiere_validacion_humana is True
        faltantes = set(resultado.campos_faltantes)
        assert {"matricula", "titular", "bastidor"}.issubset(faltantes)

    def test_campos_parciales_penaliza(self):
        datos = {"matricula": "1234 ABC"}  # falta titular y bastidor
        resultado = _parsear_respuesta(_payload("cti", 0.90, datos), None)
        assert resultado.confianza_score <= 0.5
        assert "titular" in resultado.campos_faltantes


# ── MODELO_620 ─────────────────────────────────────────────────────────────────

class TestModelo620:
    def test_completo_no_penaliza(self):
        resultado = _parsear_respuesta(_payload("modelo_620", 0.88, DATOS_COMPLETOS[TipoDocumento.MODELO_620]), None)
        assert resultado.confianza_score == 0.88
        assert resultado.campos_faltantes == []

    def test_incompleto_penaliza(self):
        resultado = _parsear_respuesta(_payload("modelo_620", 0.88, {}), None)
        assert resultado.confianza_score <= 0.5
        faltantes = set(resultado.campos_faltantes)
        assert {"importe", "transmitente", "adquirente", "fecha_devengo"}.issubset(faltantes)

    def test_solo_importe_penaliza(self):
        resultado = _parsear_respuesta(_payload("modelo_620", 0.88, {"importe": "350"}), None)
        assert resultado.confianza_score <= 0.5
        assert "transmitente" in resultado.campos_faltantes


# ── ANEXO_650 ─────────────────────────────────────────────────────────────────

class TestAnexo650:
    def test_completo_no_penaliza(self):
        resultado = _parsear_respuesta(_payload("anexo_650", 0.82, DATOS_COMPLETOS[TipoDocumento.ANEXO_650]), None)
        assert resultado.confianza_score == 0.82
        assert resultado.campos_faltantes == []

    def test_incompleto_penaliza(self):
        resultado = _parsear_respuesta(_payload("anexo_650", 0.82, {}), None)
        assert resultado.confianza_score <= 0.5
        assert "bastidor" in resultado.campos_faltantes
        assert "valor_vehiculo" in resultado.campos_faltantes


# ── DNI ───────────────────────────────────────────────────────────────────────

class TestDNI:
    def test_completo_no_penaliza(self):
        resultado = _parsear_respuesta(_payload("dni", 0.96, DATOS_COMPLETOS[TipoDocumento.DNI]), None)
        assert resultado.confianza_score == 0.96
        assert resultado.campos_faltantes == []

    def test_incompleto_penaliza(self):
        resultado = _parsear_respuesta(_payload("dni", 0.96, {}), None)
        assert resultado.confianza_score <= 0.5
        assert "nombre" in resultado.campos_faltantes
        assert "numero_documento" in resultado.campos_faltantes

    def test_solo_nombre_penaliza(self):
        resultado = _parsear_respuesta(_payload("dni", 0.96, {"nombre": "Juan"}), None)
        assert resultado.confianza_score <= 0.5
        assert "numero_documento" in resultado.campos_faltantes


# ── FICHA_TECNICA ─────────────────────────────────────────────────────────────

class TestFichaTecnica:
    def test_completo_no_penaliza(self):
        resultado = _parsear_respuesta(_payload("ficha_tecnica", 0.91, DATOS_COMPLETOS[TipoDocumento.FICHA_TECNICA]), None)
        assert resultado.confianza_score == 0.91
        assert resultado.campos_faltantes == []

    def test_incompleto_penaliza(self):
        resultado = _parsear_respuesta(_payload("ficha_tecnica", 0.91, {}), None)
        assert resultado.confianza_score <= 0.5
        assert "marca" in resultado.campos_faltantes
        assert "bastidor" in resultado.campos_faltantes


# ── evaluar_completitud_extraccion directo ────────────────────────────────────

def test_evaluar_completitud_todos_tipos_con_datos_vacios():
    """Para todos los tipos con campos requeridos, datos vacíos → incompleto."""
    from app.services.catalogo_documental import CAMPOS_REQUERIDOS
    for tipo, campos in CAMPOS_REQUERIDOS.items():
        if not campos:
            continue  # tipos sin campos: siempre completo
        completo, faltantes = evaluar_completitud_extraccion(tipo, {})
        assert not completo, f"{tipo.value} debería ser incompleto con datos vacíos"
        assert set(faltantes) == set(campos), f"{tipo.value}: faltantes incorrectos"


def test_evaluar_completitud_todos_tipos_con_datos_completos():
    """Con datos de DATOS_COMPLETOS definidos, ninguno debe penalizarse."""
    for tipo, datos in DATOS_COMPLETOS.items():
        completo, faltantes = evaluar_completitud_extraccion(tipo, datos)
        assert completo, f"{tipo.value} debería ser completo con {datos}, pero faltan {faltantes}"
