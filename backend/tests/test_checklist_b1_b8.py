"""
Tests de correcciones B1 y B8 — motor_cotejo.resolver_checklist.

B1: herencia no incluye contrato_compraventa (transmisión mortis causa).
B8: compra_empresa activa automáticamente escritura_poder + cif.
"""
from app.services.catalogo_documental import (
    FamiliaTramite, SubtipoTramite, NaturalezaPartes,
)
from app.services.motor_cotejo import resolver_checklist


# ── B1: herencia ───────────────────────────────────────────────────────────────

def test_herencia_no_incluye_contrato_compraventa():
    """Matriz §2.1 herencia: no hay contrato de compraventa (transmisión mortis causa)."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    assert "contrato_compraventa" not in cl.requisitos


def test_herencia_incluye_docs_sucesorios():
    """Sesión 13: checklist herencia confirmado — decl_responsable + modelo_650 + anexo_650."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    for doc in ("declaracion_responsable_fallecimiento", "modelo_650", "anexo_650"):
        assert doc in cl.requisitos, f"herencia debe incluir {doc}"


def test_herencia_incluye_base_sin_contrato_ni_620():
    """Sesión 13: herencia NO lleva CTI, DNI, contrato ni modelo_620 en el checklist de cotejo."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    for doc in ("contrato_compraventa", "modelo_620", "cti", "dni"):
        assert doc not in cl.requisitos, f"herencia NO debe incluir {doc}"


def test_compraventa_particular_no_incluye_docs_herencia():
    """Compraventa particular: sin documentos de herencia."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRAVENTA_PARTICULAR)
    assert "declaracion_responsable_fallecimiento" not in cl.requisitos
    assert "modelo_650" not in cl.requisitos


# ── B8: compra_empresa implica naturaleza empresa ──────────────────────────────

def test_compra_empresa_incluye_escritura_poder_y_cif():
    """Matriz §2.1 compra_empresa: subtipo debe activar escritura_poder + cif."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRA_EMPRESA)
    assert "escritura_poder" in cl.requisitos
    assert "cif" in cl.requisitos


def test_compra_empresa_sin_pasar_naturaleza_partes():
    """El llamador no necesita pasar naturaleza_partes=EMPRESA_ADQUIRENTE por separado."""
    cl_sin_param = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRA_EMPRESA)
    cl_con_param = resolver_checklist(
        FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRA_EMPRESA,
        naturaleza_partes=NaturalezaPartes.EMPRESA_ADQUIRENTE,
    )
    assert cl_sin_param.requisitos == cl_con_param.requisitos


def test_compraventa_particular_no_incluye_escritura_poder():
    """Compraventa entre particulares no debe incluir escritura_poder ni cif."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRAVENTA_PARTICULAR)
    assert "escritura_poder" not in cl.requisitos
    assert "cif" not in cl.requisitos
