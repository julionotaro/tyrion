"""
Tests del flujo de carga manual v2 (sesión 12).

Flujo correcto:
  1. POST /api/carga/documentos  → clasifica, devuelve sesion_id
  2. POST /api/carga/procesar    → deduce tipo, crea trámite
  3. El trámite aparece en GET /api/tramites (Pantalla de Control)

El tipo de trámite NO se declara: se deduce de los documentos.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento
from app.services import registro_tramites

client = TestClient(app)

PDF = b"%PDF-1.4 minimal"


@pytest.fixture(autouse=True)
def _limpiar_registro():
    """Cada test arranca con el registro limpio."""
    registro_tramites.reset()
    yield
    registro_tramites.reset()


def _clf(tipo: TipoDocumento, score: float = 0.93) -> ResultadoClasificacion:
    nivel = "ALTA" if score >= 0.85 else ("MEDIA" if score >= 0.60 else "BAJA")
    return ResultadoClasificacion(
        tipo_detectado=tipo, confianza_score=score, confianza_nivel=nivel,
        datos_extraidos={}, justificacion="Test",
    )


def _subir(tipos, score=0.93):
    """Sube documentos con clasificación mockeada. Devuelve sesion_id."""
    archivos = [
        ("archivos", (f"doc{i}.pdf", PDF, "application/pdf"))
        for i in range(len(tipos))
    ]
    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(side_effect=[_clf(t, score) for t in tipos])
        r = client.post("/api/carga/documentos", files=archivos)
    assert r.status_code == 200, r.text
    return r.json()


def test_subir_documentos_devuelve_clasificacion():
    """POST /documentos → tipo detectado por documento + sesion_id."""
    d = _subir([TipoDocumento.CTI])
    assert d["sesion_id"].startswith("sesion-")
    assert len(d["documentos"]) == 1
    assert d["documentos"][0]["tipo_detectado"] == "cti"
    assert d["documentos"][0]["confianza"] == "ALTA"


def test_procesar_deduce_transferencia_completa():
    """CTI + 620 + DNI + contrato → TRANSFERENCIA, listo_dgt."""
    d = _subir([
        TipoDocumento.CTI, TipoDocumento.MODELO_620,
        TipoDocumento.DNI, TipoDocumento.CONTRATO_COMPRAVENTA,
    ])
    r = client.post("/api/carga/procesar", json={"sesion_id": d["sesion_id"]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["tipo_tramite"] == "TRANSFERENCIA"
    assert res["listo_dgt"] is True
    assert res["estado"] == "listo_dgt"
    assert res["aviso_preparado"] is False


def test_procesar_transferencia_incompleta_pide_gestoria():
    """CTI + DNI (faltan 620 y contrato) → pendiente_gestoria + aviso."""
    d = _subir([TipoDocumento.CTI, TipoDocumento.DNI])
    r = client.post("/api/carga/procesar", json={
        "sesion_id": d["sesion_id"], "gestoria": "Gestoría Test",
    })
    res = r.json()
    assert res["tipo_tramite"] == "TRANSFERENCIA"
    assert res["listo_dgt"] is False
    assert res["estado"] == "pendiente_gestoria"
    assert res["aviso_preparado"] is True
    assert "modelo_620" in res["requisitos_faltantes"]


def test_procesar_matriculacion():
    """Solicitud matriculación → tipo MATRICULACION deducido."""
    d = _subir([
        TipoDocumento.SOLICITUD_MATRICULACION,
        TipoDocumento.FICHA_TECNICA,
    ])
    r = client.post("/api/carga/procesar", json={"sesion_id": d["sesion_id"]})
    res = r.json()
    assert res["tipo_tramite"] == "MATRICULACION"


def test_tramite_creado_aparece_en_pantalla_control():
    """El trámite procesado aparece en GET /api/tramites."""
    d = _subir([
        TipoDocumento.CTI, TipoDocumento.MODELO_620,
        TipoDocumento.DNI, TipoDocumento.CONTRATO_COMPRAVENTA,
    ])
    r = client.post("/api/carga/procesar", json={"sesion_id": d["sesion_id"]})
    tramite_id = r.json()["tramite_id"]

    # Debe aparecer en la lista de la Pantalla de Control
    tramites = client.get("/api/tramites").json()
    ids = [t["id"] for t in tramites]
    assert tramite_id in ids

    # Y su detalle debe ser accesible
    detalle = client.get(f"/api/tramites/{tramite_id}")
    assert detalle.status_code == 200
    assert detalle.json()["id"] == tramite_id


def test_tramite_manual_cuenta_en_salud():
    """procesados_hoy en /api/salud refleja el trámite creado."""
    salud_antes = client.get("/api/salud").json()["procesados_hoy"]
    d = _subir([TipoDocumento.SOLICITUD_BAJA, TipoDocumento.DNI])
    client.post("/api/carga/procesar", json={"sesion_id": d["sesion_id"]})
    salud_despues = client.get("/api/salud").json()["procesados_hoy"]
    assert salud_despues == salud_antes + 1


def test_documentos_sin_tipo_claro_van_a_revision():
    """Solo DNI (sin documento principal) → trámite en revisión manual."""
    d = _subir([TipoDocumento.DNI])
    r = client.post("/api/carga/procesar", json={"sesion_id": d["sesion_id"]})
    res = r.json()
    assert res["tipo_tramite"] is None
    assert res["estado"] == "en_revision"


def test_procesar_sesion_inexistente_da_404():
    r = client.post("/api/carga/procesar", json={"sesion_id": "no-existe"})
    assert r.status_code == 404


def test_get_sesion_devuelve_estado():
    """GET /api/carga/sesion/{id} → documentos + tramite_id tras procesar."""
    d = _subir([TipoDocumento.CTI, TipoDocumento.DNI])
    sesion_id = d["sesion_id"]
    r1 = client.get(f"/api/carga/sesion/{sesion_id}")
    assert r1.status_code == 200
    assert r1.json()["num_documentos"] == 2
    assert r1.json()["tramite_id"] is None

    proc = client.post("/api/carga/procesar", json={"sesion_id": sesion_id})
    tramite_id = proc.json()["tramite_id"]
    r2 = client.get(f"/api/carga/sesion/{sesion_id}")
    assert r2.json()["tramite_id"] == tramite_id


def test_subir_varios_a_misma_sesion():
    """Subir en dos tandas a la misma sesión acumula documentos."""
    d1 = _subir([TipoDocumento.CTI])
    sesion_id = d1["sesion_id"]
    # Segunda tanda a la misma sesión
    with patch("app.api.carga._clf") as mock_clf:
        mock_clf.clasificar = AsyncMock(side_effect=[_clf(TipoDocumento.MODELO_620)])
        r = client.post(
            "/api/carga/documentos",
            files=[("archivos", ("doc.pdf", PDF, "application/pdf"))],
            data={"sesion_id": sesion_id},
        )
    assert r.json()["sesion_id"] == sesion_id
    sesion = client.get(f"/api/carga/sesion/{sesion_id}").json()
    assert sesion["num_documentos"] == 2
