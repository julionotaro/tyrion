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
    """Matriz §2.1 herencia: deben aparecer los cuatro documentos de sucesión."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    for doc in ("certificado_defuncion", "modelo_650", "declaracion_herederos", "anexo_650"):
        assert doc in cl.requisitos, f"herencia debe incluir {doc}"


def test_herencia_incluye_base_sin_contrato():
    """Herencia conserva cti, modelo_620 y dni del base."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    for doc in ("cti", "modelo_620", "dni"):
        assert doc in cl.requisitos, f"herencia debe incluir {doc}"


def test_compraventa_particular_sigue_incluyendo_contrato():
    """Compraventa particular mantiene contrato_compraventa."""
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.COMPRAVENTA_PARTICULAR)
    assert "contrato_compraventa" in cl.requisitos


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
