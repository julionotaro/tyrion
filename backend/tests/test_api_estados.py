"""
Tests de regresión para API de estados y acciones de escalado.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_stats_devuelve_alertas_numerico():
    """GET /api/stats → campo alertas es entero >= 0."""
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "alertas" in data
    assert isinstance(data["alertas"], int)
    assert data["alertas"] >= 0


def test_stats_devuelve_todos_los_campos_requeridos():
    """GET /api/stats → todos los campos de StatsResponse presentes."""
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    for campo in ("conteos", "etiquetas", "total", "alertas",
                  "total_planificados", "sin_match", "pendiente_jefatura", "sin_documentacion"):
        assert campo in data, f"Campo '{campo}' ausente en /api/stats"


def test_escalar_tramite_pendiente_gestoria():
    """POST /api/tramites/{id}/escalar en estado pendiente_gestoria → 200."""
    # tramite en datos_prueba con estado pendiente_gestoria
    tramites = client.get("/api/tramites?estado=pendiente_gestoria").json()
    if not tramites:
        pytest.skip("No hay trámites en pendiente_gestoria en datos de prueba")
    tramite_id = tramites[0]["id"]
    resp = client.post(f"/api/tramites/{tramite_id}/escalar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["tramite_id"] == tramite_id


def test_escalar_tramite_no_pendiente_gestoria_da_400():
    """POST /api/tramites/{id}/escalar en estado incorrecto → 400."""
    tramites = client.get("/api/tramites").json()
    # Buscar un trámite que NO sea pendiente_gestoria
    t = next((t for t in tramites if t["estado"] != "pendiente_gestoria"), None)
    if not t:
        pytest.skip("Todos los trámites están en pendiente_gestoria")
    resp = client.post(f"/api/tramites/{t['id']}/escalar")
    assert resp.status_code == 400


def test_escalar_tramite_inexistente_da_404():
    """POST /api/tramites/inexistente/escalar → 404."""
    resp = client.post("/api/tramites/tramite-inexistente-xyz/escalar")
    assert resp.status_code == 404


def test_planilla_sin_match_devuelve_lista():
    """GET /api/planilla/sin-match → lista + total entero."""
    resp = client.get("/api/planilla/sin-match")
    assert resp.status_code == 200
    data = resp.json()
    assert "emails_sin_match" in data
    assert "total" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["emails_sin_match"], list)


def test_planilla_hoy_devuelve_conteos():
    """GET /api/planilla/hoy → campos de conteo presentes."""
    resp = client.get("/api/planilla/hoy")
    assert resp.status_code == 200
    data = resp.json()
    for campo in ("fecha", "tipo", "total_planificados", "sin_documentacion",
                  "con_documentacion", "validados", "escalados"):
        assert campo in data, f"Campo '{campo}' ausente en /api/planilla/hoy"
    assert data["total_planificados"] >= 0
