"""
Tests de la API de Pantalla Control.

Usan TestClient de FastAPI con datos de prueba (USE_DATOS_PRUEBA=true).
Sin BD real ni red: todo es determinista con los 8 trámites hardcodeados.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /api/stats ──

def test_stats_devuelve_seis_estados():
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert set(data["conteos"].keys()) == {
        "recibido", "en_revision", "pendiente_gestoria",
        "listo_dgt", "en_cadeteria", "cerrado",
    }


def test_stats_total_igual_a_datos_prueba():
    r = client.get("/api/stats")
    data = r.json()
    assert data["total"] == 8


def test_stats_alertas_son_los_esperados():
    r = client.get("/api/stats")
    data = r.json()
    # t-003 y t-008 tienen alerta=True en datos_prueba
    assert data["alertas"] == 2


def test_stats_etiquetas_incluidas():
    r = client.get("/api/stats")
    data = r.json()
    assert "pendiente_gestoria" in data["etiquetas"]
    assert data["etiquetas"]["cerrado"] == "Cerrado"


# ── /api/tramites ──

def test_lista_tramites_sin_filtros():
    r = client.get("/api/tramites")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8


def test_filtro_por_estado():
    r = client.get("/api/tramites?estado=pendiente_gestoria")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3  # t-003, t-004, t-008
    for t in data:
        assert t["estado"] == "pendiente_gestoria"


def test_filtro_por_tipo():
    r = client.get("/api/tramites?tipo=BAJA")
    assert r.status_code == 200
    data = r.json()
    for t in data:
        assert t["tipo"] == "BAJA"


def test_filtro_por_gestoria():
    r = client.get("/api/tramites?gestoria=L%C3%B3pez")
    assert r.status_code == 200
    data = r.json()
    for t in data:
        assert "López" in t["gestoria"]


def test_tramite_resumen_tiene_campos_requeridos():
    r = client.get("/api/tramites")
    t = r.json()[0]
    for campo in ["id", "tipo", "gestoria", "estado", "estado_label", "fecha_entrada", "alerta", "num_docs"]:
        assert campo in t, f"Campo '{campo}' ausente en resumen"


def test_estado_label_presente():
    r = client.get("/api/tramites")
    for t in r.json():
        assert t["estado_label"]  # nunca vacío


# ── /api/tramites/{id} ──

def test_detalle_tramite_existente():
    r = client.get("/api/tramites/t-001")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "t-001"
    assert "documentos" in data
    assert "historial" in data
    assert "avisos_pendientes" in data


def test_detalle_tramite_inexistente_404():
    r = client.get("/api/tramites/no-existe")
    assert r.status_code == 404


def test_detalle_incluye_gestoria_email():
    r = client.get("/api/tramites/t-001")
    assert "gestoria_email" in r.json()


def test_detalle_tramite_cerrado_tiene_comprobante():
    r = client.get("/api/tramites/t-007")
    data = r.json()
    assert data["num_comprobante_dgt"] == "DGT-2026-00123"


def test_detalle_documentos_tienen_validez():
    r = client.get("/api/tramites/t-003")
    docs = r.json()["documentos"]
    for doc in docs:
        assert doc["validez"] in ("VALIDO", "EVIDENCIA_COMPATIBLE", "RECHAZADO", "NO_APLICA")


# ── /api/tramites/{id}/escalar ──

def test_escalar_tramite_en_pendiente():
    r = client.post("/api/tramites/t-004/escalar")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tramite_id"] == "t-004"


def test_escalar_tramite_en_estado_incorrecto():
    r = client.post("/api/tramites/t-001/escalar")  # estado=recibido
    assert r.status_code == 400


def test_escalar_tramite_inexistente():
    r = client.post("/api/tramites/no-existe/escalar")
    assert r.status_code == 404


# ── Cobertura de macro-estados ──

def test_todos_los_macroestados_tienen_al_menos_un_tramite():
    """Los datos de prueba cubren los 6 macro-estados."""
    r = client.get("/api/stats")
    conteos = r.json()["conteos"]
    for estado, n in conteos.items():
        assert n >= 1, f"Estado '{estado}' sin trámites de prueba"
