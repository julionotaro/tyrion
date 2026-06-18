"""Tests CRUD de gestorías via API + coherencia con nombre_gestoria()."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import gestorias as store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


# ── GET /api/gestorias ────────────────────────────────────────────────────────

def test_listar_devuelve_seed():
    resp = client.get("/api/gestorias")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    emails = [g["email"] for g in data]
    assert "jlogistic3000@gmail.com" in emails


def test_listar_tiene_campos_obligatorios():
    resp = client.get("/api/gestorias")
    for g in resp.json():
        assert "email" in g
        assert "nombre" in g


# ── POST /api/gestorias ───────────────────────────────────────────────────────

def test_crear_gestoria_nueva():
    payload = {"email": "nueva@test.es", "nombre": "Gestoria Nueva", "contacto": "Ana", "telefono": "600000001"}
    resp = client.post("/api/gestorias", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "nueva@test.es"
    assert data["nombre"] == "Gestoria Nueva"
    assert data["contacto"] == "Ana"
    assert data["telefono"] == "600000001"


def test_crear_gestoria_aparece_en_listar():
    client.post("/api/gestorias", json={"email": "nueva2@test.es", "nombre": "Test2"})
    resp = client.get("/api/gestorias")
    emails = [g["email"] for g in resp.json()]
    assert "nueva2@test.es" in emails


def test_crear_email_duplicado_409():
    client.post("/api/gestorias", json={"email": "dup@test.es", "nombre": "Primera"})
    resp = client.post("/api/gestorias", json={"email": "dup@test.es", "nombre": "Segunda"})
    assert resp.status_code == 409


def test_crear_normaliza_email_a_minusculas():
    resp = client.post("/api/gestorias", json={"email": "MAYUS@Test.ES", "nombre": "Mayus"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "mayus@test.es"


# ── PUT /api/gestorias/{email} ────────────────────────────────────────────────

def test_actualizar_nombre():
    client.post("/api/gestorias", json={"email": "edit@test.es", "nombre": "Original"})
    resp = client.put("/api/gestorias/edit@test.es", json={"nombre": "Actualizado"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Actualizado"


def test_actualizar_campos_parciales():
    client.post("/api/gestorias", json={"email": "parcial@test.es", "nombre": "Orig", "telefono": "600"})
    resp = client.put("/api/gestorias/parcial@test.es", json={"contacto": "Pedro"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["contacto"] == "Pedro"
    assert data["nombre"] == "Orig"          # sin cambio
    assert data["telefono"] == "600"          # sin cambio


def test_actualizar_inexistente_404():
    resp = client.put("/api/gestorias/noexiste@test.es", json={"nombre": "X"})
    assert resp.status_code == 404


# ── DELETE /api/gestorias/{email} ─────────────────────────────────────────────

def test_eliminar_gestoria():
    client.post("/api/gestorias", json={"email": "del@test.es", "nombre": "Borrar"})
    resp = client.delete("/api/gestorias/del@test.es")
    assert resp.status_code == 204
    # Ya no aparece en listar
    emails = [g["email"] for g in client.get("/api/gestorias").json()]
    assert "del@test.es" not in emails


def test_eliminar_inexistente_404():
    resp = client.delete("/api/gestorias/fantasma@test.es")
    assert resp.status_code == 404


# ── nombre_gestoria() refleja cambios del store ───────────────────────────────

def test_nombre_gestoria_refleja_creacion():
    from app.services.gestorias import nombre_gestoria
    client.post("/api/gestorias", json={"email": "nuevo@x.es", "nombre": "Gestoría X"})
    assert nombre_gestoria("nuevo@x.es") == "Gestoría X"


def test_nombre_gestoria_refleja_actualizacion():
    from app.services.gestorias import nombre_gestoria
    client.post("/api/gestorias", json={"email": "cambio@x.es", "nombre": "Antes"})
    client.put("/api/gestorias/cambio@x.es", json={"nombre": "Después"})
    assert nombre_gestoria("cambio@x.es") == "Después"


def test_nombre_gestoria_refleja_eliminacion():
    from app.services.gestorias import nombre_gestoria
    client.post("/api/gestorias", json={"email": "borrado@x.es", "nombre": "Borrado"})
    client.delete("/api/gestorias/borrado@x.es")
    # Tras eliminar → fallback, no el nombre previo
    resultado = nombre_gestoria("borrado@x.es")
    assert resultado != "Borrado"
