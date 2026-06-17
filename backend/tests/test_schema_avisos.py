"""
Tests: schema fijo de avisos y alineación con el frontend.

El frontend (index.html) lee a.tipo, a.enviado_at, a.requisito.
El backend debe emitir exactamente esas claves, sin None.
"""
from app.schemas.avisos import AvisoPendiente
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento
from app.services import registro_tramites
from app.api import store

client = TestClient(app)
PDF = b"%PDF-1.4 minimal"


def test_aviso_pendiente_schema_claves():
    """AvisoPendiente tiene las tres claves que espera el frontend."""
    aviso = AvisoPendiente(tipo="AVISO_1", enviado_at="2026-01-01T00:00:00Z", requisito="modelo_620")
    d = aviso.model_dump()
    assert "tipo" in d and d["tipo"] is not None
    assert "enviado_at" in d and d["enviado_at"] is not None
    assert "requisito" in d and d["requisito"] is not None
    assert "asunto" not in d       # clave que NO debe existir
    assert "preparado_at" not in d  # clave que NO debe existir


def test_aviso_serializa_sin_none():
    """Ningún campo del aviso es None."""
    aviso = AvisoPendiente(tipo="AVISO_2", enviado_at="2026-06-17T10:00:00Z", requisito="cti")
    for k, v in aviso.model_dump().items():
        assert v is not None, f"Campo '{k}' es None"


def _clf(tipo: TipoDocumento) -> ResultadoClasificacion:
    return ResultadoClasificacion(
        tipo_detectado=tipo, confianza_score=0.93, confianza_nivel="ALTA",
        datos_extraidos={}, justificacion="Test",
    )


def _setup_fixture(reset=True):
    if reset:
        registro_tramites.reset()
        store.reset()


def test_tramite_con_faltantes_emite_avisos_canónicos():
    """Trámite procesado con faltantes emite avisos con tipo/enviado_at/requisito."""
    _setup_fixture()
    archivos = [("archivos", ("doc.pdf", PDF, "application/pdf"))]
    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(side_effect=[_clf(TipoDocumento.CTI)])
        r = client.post("/api/carga/documentos", files=archivos)
    sesion_id = r.json()["sesion_id"]

    proc = client.post("/api/carga/procesar", json={
        "sesion_id": sesion_id, "gestoria": "Gestoría Test",
    })
    assert proc.status_code == 200
    tramite_id = proc.json()["tramite_id"]

    # Obtener el trámite de la Pantalla de Control
    tramite = client.get(f"/api/tramites/{tramite_id}").json()
    for aviso in tramite.get("avisos_pendientes", []):
        assert "tipo" in aviso, "falta clave 'tipo'"
        assert "enviado_at" in aviso, "falta clave 'enviado_at' (frontend lee esta)"
        assert "requisito" in aviso, "falta clave 'requisito' (frontend lee esta)"
        assert aviso["tipo"] is not None
        assert aviso["enviado_at"] is not None
        assert aviso["requisito"] is not None
        assert "preparado_at" not in aviso, "clave 'preparado_at' no debe existir"
        assert "asunto" not in aviso, "clave 'asunto' no debe existir"
    _setup_fixture()
