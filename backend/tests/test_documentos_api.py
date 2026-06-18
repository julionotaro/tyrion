"""Tests para los endpoints de documentos (Split-view documental)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_listar_documentos_tramite_existente():
    resp = client.get("/api/tramites/t-001/documentos")
    assert resp.status_code == 200
    docs = resp.json()
    assert isinstance(docs, list)
    assert len(docs) > 0
    doc = docs[0]
    assert "nombre" in doc
    assert "validez" in doc
    assert "tiene_extraccion" in doc


def test_listar_documentos_tramite_inexistente():
    resp = client.get("/api/tramites/NO-EXISTE/documentos")
    assert resp.status_code == 404


def test_documentos_con_extraccion_tienen_id():
    resp = client.get("/api/tramites/t-001/documentos")
    assert resp.status_code == 200
    docs = resp.json()
    for doc in docs:
        if doc["tiene_extraccion"]:
            assert doc["id"] is not None
        # docs sin extraccion pueden tener id None
        if doc["id"] is None:
            assert doc["tiene_extraccion"] is False


def test_extraccion_documento_existente():
    resp = client.get("/api/documentos/doc-001/extraccion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "doc-001"
    assert "campos_extraidos" in data
    assert len(data["campos_extraidos"]) > 0
    assert "justificacion" in data
    assert "confianza_score" in data
    campo = data["campos_extraidos"][0]
    assert "campo" in campo
    assert "valor" in campo
    assert "estado" in campo
    assert campo["estado"] in ("valido", "evidencia", "rechazado", "ilegible")


def test_extraccion_documento_inexistente():
    resp = client.get("/api/documentos/doc-NOPE/extraccion")
    assert resp.status_code == 404


def test_extraccion_documento_evidencia_compatible():
    """doc-009 es Anexo 650 con bastidor incorrecto → EVIDENCIA_COMPATIBLE."""
    resp = client.get("/api/documentos/doc-009/extraccion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["validez"] == "EVIDENCIA_COMPATIBLE"


def test_extraccion_documento_rechazado():
    """doc-007 es hoja_caja → RECHAZADO."""
    resp = client.get("/api/documentos/doc-007/extraccion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["validez"] == "RECHAZADO"


def test_archivo_documento_sin_archivo():
    resp = client.get("/api/documentos/doc-002/archivo")
    # doc-002 no tiene archivo en datos de prueba → 503
    assert resp.status_code in (503, 404)


def test_archivo_documento_inexistente():
    resp = client.get("/api/documentos/doc-NOPE/archivo")
    assert resp.status_code == 404


def test_campos_extraidos_estados_validos():
    """Todos los campos extraídos deben tener estados reconocidos."""
    for doc_id in ("doc-001", "doc-003", "doc-009", "doc-007"):
        resp = client.get(f"/api/documentos/{doc_id}/extraccion")
        assert resp.status_code == 200
        for campo in resp.json()["campos_extraidos"]:
            assert campo["estado"] in ("valido", "evidencia", "rechazado", "ilegible"), \
                f"{doc_id}: estado inesperado '{campo['estado']}'"


def test_listar_documentos_otro_tramite():
    resp = client.get("/api/tramites/t-002/documentos")
    assert resp.status_code == 200
    docs = resp.json()
    assert isinstance(docs, list)
    assert len(docs) > 0
