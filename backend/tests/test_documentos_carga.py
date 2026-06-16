"""
Tests: documentos cargados via /api/carga son accesibles en /api/documentos.

Verifica que GET /api/documentos/{doc_id}/extraccion NO devuelve 404
para IDs generados por /api/carga/procesar.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento
from app.services import registro_tramites
from app.api import store

client = TestClient(app)

PDF = b"%PDF-1.4 minimal"


@pytest.fixture(autouse=True)
def _limpiar():
    registro_tramites.reset()
    store.reset()
    yield
    registro_tramites.reset()
    store.reset()


def _clf(tipo: TipoDocumento, score: float = 0.93) -> ResultadoClasificacion:
    nivel = "ALTA" if score >= 0.85 else ("MEDIA" if score >= 0.60 else "BAJA")
    return ResultadoClasificacion(
        tipo_detectado=tipo, confianza_score=score, confianza_nivel=nivel,
        datos_extraidos={"matricula": "1234ABC"}, justificacion="Test",
    )


def _subir_y_procesar(tipos):
    """Sube documentos y procesa la sesión. Devuelve (sesion_id, resultado_procesar)."""
    archivos = [
        ("archivos", (f"doc{i}.pdf", PDF, "application/pdf"))
        for i in range(len(tipos))
    ]
    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(side_effect=[_clf(t) for t in tipos])
        r = client.post("/api/carga/documentos", files=archivos)
    assert r.status_code == 200, r.text
    sesion_id = r.json()["sesion_id"]
    proc = client.post("/api/carga/procesar", json={"sesion_id": sesion_id})
    assert proc.status_code == 200, proc.text
    return sesion_id, proc.json()


def test_extraccion_documento_carga_200():
    """GET extraccion devuelve 200 (no 404) para doc_id generado por /carga."""
    _, proc = _subir_y_procesar([TipoDocumento.CTI, TipoDocumento.DNI])
    doc_ids = [d["doc_id"] for d in proc["documentos"]]
    assert doc_ids, "No hay documentos en la respuesta de procesar"
    r = client.get(f"/api/documentos/{doc_ids[0]}/extraccion")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == doc_ids[0]
    assert data["tramite_id"] == proc["tramite_id"]


def test_extraccion_campos_extraidos():
    """Los campos extraídos del clasificador aparecen en la extracción."""
    _, proc = _subir_y_procesar([TipoDocumento.CTI])
    doc_id = proc["documentos"][0]["doc_id"]
    data = client.get(f"/api/documentos/{doc_id}/extraccion").json()
    assert data["campos_extraidos"][0]["campo"] == "matricula"
    assert data["campos_extraidos"][0]["valor"] == "1234ABC"


def test_listar_documentos_tramite_carga():
    """GET /tramites/{id}/documentos funciona para trámites de carga."""
    _, proc = _subir_y_procesar([
        TipoDocumento.CTI, TipoDocumento.MODELO_620,
        TipoDocumento.DNI, TipoDocumento.CONTRATO_COMPRAVENTA,
    ])
    tramite_id = proc["tramite_id"]
    r = client.get(f"/api/tramites/{tramite_id}/documentos")
    assert r.status_code == 200, r.text
    docs = r.json()
    assert len(docs) == 4
    assert all(d["tiene_extraccion"] for d in docs)


def test_extraccion_doc_inexistente_404():
    """Documento con ID inventado sigue devolviendo 404."""
    r = client.get("/api/documentos/doc-xxxxxxxx/extraccion")
    assert r.status_code == 404
