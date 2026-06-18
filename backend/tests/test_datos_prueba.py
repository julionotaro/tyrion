"""Tests de coherencia sobre los datos de prueba hardcodeados."""
from app.api.datos_prueba import TRAMITES_PRUEBA, DOCUMENTOS_PRUEBA


def test_ningún_documento_de_tramite_es_permiso_circulacion_de_entrada():
    """El permiso_circulacion es documento de SALIDA — nunca debe aparecer como entrada."""
    for t in TRAMITES_PRUEBA:
        for doc in t.get("documentos", []):
            tipo = doc.get("tipo_detectado", "")
            assert tipo != "permiso_circulacion", (
                f"Trámite {t['id']} tiene permiso_circulacion como documento de entrada. "
                "Es un documento de salida que imprime el Colegio."
            )


def test_ningún_documento_prueba_dict_es_permiso_circulacion_de_entrada():
    """El dict DOCUMENTOS_PRUEBA tampoco debe tener permiso_circulacion como tipo_detectado
    excepto en casos de rechazo donde es el tipo *requerido* (no el recibido)."""
    for doc_id, doc in DOCUMENTOS_PRUEBA.items():
        tipo = doc.get("tipo_detectado", "")
        assert tipo != "permiso_circulacion", (
            f"DOCUMENTOS_PRUEBA[{doc_id}] tiene tipo_detectado=permiso_circulacion. "
            "No debe aparecer como tipo clasificado de un documento entrante."
        )


def test_tramites_avanzados_tienen_verificaciones():
    """Los trámites en estados avanzados deben tener verificaciones para el panel cotejo."""
    estados_avanzados = {"en_revision", "listo_dgt", "en_cadeteria", "cerrado", "pendiente_gestoria"}
    excluir = {"t-001", "t-004"}  # recibido y baja pendiente sin cotejo complejo
    for t in TRAMITES_PRUEBA:
        if t["id"] in excluir:
            continue
        if t["estado"] in estados_avanzados:
            assert t.get("verificaciones"), (
                f"Trámite {t['id']} (estado={t['estado']}) no tiene verificaciones[]."
            )


def test_t001_no_tiene_verificaciones():
    """t-001 está recibido — aún no procesado, no tiene verificaciones."""
    t001 = next(t for t in TRAMITES_PRUEBA if t["id"] == "t-001")
    assert not t001.get("verificaciones"), "t-001 no debería tener verificaciones (recibido)"


def test_t008_tiene_verificacion_negativa():
    """t-008 tiene un documento rechazado — debe haber al menos una verificación ok=False."""
    t008 = next(t for t in TRAMITES_PRUEBA if t["id"] == "t-008")
    verifs = t008.get("verificaciones", [])
    assert verifs, "t-008 debe tener verificaciones"
    assert any(not v["ok"] for v in verifs), "t-008 debe tener al menos una verificación negativa"
