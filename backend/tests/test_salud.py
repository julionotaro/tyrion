"""
Tests para el endpoint GET /api/salud.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_salud_devuelve_estructura():
    """GET /api/salud → campos requeridos presentes."""
    r = client.get("/api/salud")
    assert r.status_code == 200
    d = r.json()
    for campo in ("activo", "clasificador", "modelo", "procesados_hoy", "ultima_actividad"):
        assert campo in d, f"Campo '{campo}' ausente en /api/salud"


def test_salud_activo_es_bool():
    """activo debe ser booleano True."""
    r = client.get("/api/salud")
    d = r.json()
    assert d["activo"] is True


def test_salud_clasificador_es_string_valido():
    """clasificador debe ser 'anthropic', 'openai' o 'mock'."""
    r = client.get("/api/salud")
    d = r.json()
    assert d["clasificador"] in ("anthropic", "openai", "mock")


def test_salud_procesados_hoy_es_entero():
    """procesados_hoy debe ser entero >= 0."""
    r = client.get("/api/salud")
    d = r.json()
    assert isinstance(d["procesados_hoy"], int)
    assert d["procesados_hoy"] >= 0


def test_salud_sin_api_keys_es_mock():
    """Sin ninguna API key configurada → clasificador = 'mock'."""
    from unittest.mock import patch
    from app.core.config import Settings
    settings_sin_key = Settings(anthropic_api_key="", openai_api_key="")
    with patch("app.api.control.get_settings", return_value=settings_sin_key):
        r = client.get("/api/salud")
    d = r.json()
    assert d["clasificador"] == "mock"


def test_salud_con_openai_key():
    """Con OPENAI_API_KEY configurada → clasificador = 'openai'."""
    from unittest.mock import patch
    from app.core.config import Settings
    settings_openai = Settings(openai_api_key="sk-test-fake", anthropic_api_key="")
    with patch("app.api.control.get_settings", return_value=settings_openai):
        r = client.get("/api/salud")
    d = r.json()
    assert d["clasificador"] == "openai"
    assert d["modelo"] == settings_openai.clasificador_openai_model
