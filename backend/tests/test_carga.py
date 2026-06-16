"""
Tests para el endpoint de carga manual de documentos.

Verifica que:
  - Crear trámite devuelve tramite_id válido
  - Subir documento dispara clasificación + cotejo y devuelve resultado
  - El resultado del trámite refleja los documentos cargados
"""
import io
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento

client = TestClient(app)

PDF_MINIMO = b"%PDF-1.4 1 0 obj<</Type/Catalog>>stream\nendstream\nendobj"


def _clf_result(tipo: TipoDocumento, score: float = 0.92) -> ResultadoClasificacion:
    nivel = "ALTA" if score >= 0.85 else ("MEDIA" if score >= 0.60 else "BAJA")
    return ResultadoClasificacion(
        tipo_detectado=tipo, confianza_score=score, confianza_nivel=nivel,
        datos_extraidos={"matricula": "1234ABC"}, justificacion="Test",
    )


def test_crear_tramite_manual():
    """POST /api/carga/tramite → 201 con tramite_id."""
    r = client.post("/api/carga/tramite", data={
        "tipo": "transferencia", "gestoria": "Gestoría Test",
    })
    assert r.status_code == 201
    d = r.json()
    assert "tramite_id" in d
    assert d["tramite_id"].startswith("manual-")
    assert d["tipo"] == "transferencia"


def test_crear_tramite_tipo_invalido():
    """Tipo desconocido → 422."""
    r = client.post("/api/carga/tramite", data={
        "tipo": "tipo_inventado", "gestoria": "G",
    })
    assert r.status_code == 422


def test_crear_tramite_sin_gestoria():
    """Sin gestoría → 422 (campo requerido)."""
    r = client.post("/api/carga/tramite", data={"tipo": "baja"})
    assert r.status_code == 422


def test_subir_documento_dispara_clasificacion():
    """POST /api/carga/tramite/{id}/documento → tipo detectado + validez."""
    # Crear trámite primero
    r = client.post("/api/carga/tramite", data={
        "tipo": "transferencia", "gestoria": "G", "matricula": "1234ABC",
    })
    tramite_id = r.json()["tramite_id"]

    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(return_value=_clf_result(TipoDocumento.CTI, 0.92))
        r2 = client.post(
            f"/api/carga/tramite/{tramite_id}/documento",
            files={"archivo": ("cti.pdf", PDF_MINIMO, "application/pdf")},
        )

    assert r2.status_code == 200
    d = r2.json()
    assert d["tipo_detectado"] == "cti"
    assert d["confianza"] == "ALTA"
    assert "validez" in d
    assert "campos_extraidos" in d


def test_subir_documento_tramite_inexistente():
    """Subir a trámite inexistente → 404."""
    r = client.post(
        "/api/carga/tramite/no-existe/documento",
        files={"archivo": ("x.pdf", PDF_MINIMO, "application/pdf")},
    )
    assert r.status_code == 404


def test_resultado_transferencia_completa():
    """CTI + 620 + DNI + contrato → listo_dgt=True."""
    r = client.post("/api/carga/tramite", data={
        "tipo": "transferencia", "gestoria": "G",
    })
    tramite_id = r.json()["tramite_id"]

    tipos = [
        TipoDocumento.CTI, TipoDocumento.MODELO_620,
        TipoDocumento.DNI, TipoDocumento.CONTRATO_COMPRAVENTA,
    ]
    for i, tipo in enumerate(tipos):
        with patch("app.api.carga._clf") as mock_clf:
            mock_clf.clasificar = AsyncMock(return_value=_clf_result(tipo))
            client.post(
                f"/api/carga/tramite/{tramite_id}/documento",
                files={"archivo": (f"doc{i}.pdf", PDF_MINIMO, "application/pdf")},
            )

    r_res = client.get(f"/api/carga/tramite/{tramite_id}/resultado")
    assert r_res.status_code == 200
    d = r_res.json()
    assert d["completo"] is True
    assert d["listo_dgt"] is True
    assert d["debe_pedir_gestoria"] is False


def test_resultado_con_doc_faltante():
    """Solo CTI en transferencia → no completo, debe_pedir_gestoria=True."""
    r = client.post("/api/carga/tramite", data={
        "tipo": "transferencia", "gestoria": "G",
    })
    tramite_id = r.json()["tramite_id"]

    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(return_value=_clf_result(TipoDocumento.CTI))
        client.post(
            f"/api/carga/tramite/{tramite_id}/documento",
            files={"archivo": ("cti.pdf", PDF_MINIMO, "application/pdf")},
        )

    r_res = client.get(f"/api/carga/tramite/{tramite_id}/resultado")
    d = r_res.json()
    assert d["completo"] is False
    assert d["listo_dgt"] is False
    assert d["debe_pedir_gestoria"] is True
    assert "modelo_620" in d["requisitos_faltantes"]


def test_resultado_tramite_inexistente():
    """GET resultado de trámite inexistente → 404."""
    r = client.get("/api/carga/tramite/no-existe/resultado")
    assert r.status_code == 404
