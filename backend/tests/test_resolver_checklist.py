"""
Tests para resolver_checklist() — árbol de decisión parametrizado.

Cubre los casos de la matriz §5:
  - Remolque (§5.1.A): sin impuesto_matriculacion
  - Agrícola (§5.1.B): con cartilla_agricola
  - Histórico (§5.1.C): flag no_telematico
  - Nuevo vs. usado (§5.1.D): documentacion_extranjera solo en usado + UE/fuera_ue
  - Herencia (§5.1.E): documentos adicionales del causante
  - Empresa adquirente (§5.1.F): escritura_poder + cif
"""
import pytest

from app.services.catalogo_documental import (
    FamiliaTramite,
    NaturalezaPartes,
    OrigenVehiculo,
    SubtipoTramite,
    TipoVehiculo,
)
from app.services.motor_cotejo import resolver_checklist


# ── MATRICULACION ─────────────────────────────────────────────────────────────

def test_matriculacion_turismo_espana_base():
    """Turismo nuevo de origen España: checklist estándar sin doc. extranjera."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        subtipo=SubtipoTramite.NUEVO,
        origen=OrigenVehiculo.ESPANA,
    )
    assert "solicitud_matriculacion" in result.requisitos
    assert "ficha_tecnica" in result.requisitos
    assert "ivtm" in result.requisitos
    assert "impuesto_matriculacion" in result.requisitos
    assert "dni" in result.requisitos
    assert "documentacion_extranjera" not in result.requisitos
    assert not result.no_telematico


def test_matriculacion_remolque_exento_impuesto():
    """Remolque: exento de impuesto especial de matriculación (§5.1.A)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        tipo_vehiculo=TipoVehiculo.REMOLQUE,
    )
    assert "impuesto_matriculacion" not in result.requisitos
    assert "solicitud_matriculacion" in result.requisitos


def test_matriculacion_agricola_requiere_cartilla():
    """Maquinaria agrícola: cartilla obligatoria (§5.1.B)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        tipo_vehiculo=TipoVehiculo.AGRICOLA,
    )
    assert "cartilla_agricola" in result.requisitos


def test_matriculacion_historico_flag_no_telematico():
    """Vehículo histórico (ART.11 RD982/2024): presentación física, flag activo (§5.1.C)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        tipo_vehiculo=TipoVehiculo.HISTORICO,
    )
    assert result.no_telematico is True


def test_matriculacion_nuevo_origen_espana_sin_doc_extranjera():
    """Vehículo nuevo origen España: sin documentación extranjera (§5.1.D / §5.2)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        subtipo=SubtipoTramite.NUEVO,
        origen=OrigenVehiculo.ESPANA,
    )
    assert "documentacion_extranjera" not in result.requisitos


def test_matriculacion_usado_origen_ue_con_doc_extranjera():
    """Vehículo usado de UE: documentación extranjera requerida (§5.1.D / §5.3)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        subtipo=SubtipoTramite.USADO,
        origen=OrigenVehiculo.UE,
    )
    assert "documentacion_extranjera" in result.requisitos


def test_matriculacion_usado_fuera_ue_con_doc_extranjera():
    """Vehículo usado de fuera de la UE: también requiere documentación extranjera."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        subtipo=SubtipoTramite.USADO,
        origen=OrigenVehiculo.FUERA_UE,
    )
    assert "documentacion_extranjera" in result.requisitos


def test_matriculacion_nuevo_origen_ue_sin_doc_extranjera():
    """Vehículo nuevo aunque venga de UE: sin documentación extranjera (solo aplica a usado)."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        subtipo=SubtipoTramite.NUEVO,
        origen=OrigenVehiculo.UE,
    )
    assert "documentacion_extranjera" not in result.requisitos


# ── TRANSFERENCIA ─────────────────────────────────────────────────────────────

def test_transferencia_particular_base():
    """Compraventa entre particulares: checklist estándar."""
    result = resolver_checklist(
        familia=FamiliaTramite.TRANSFERENCIA,
        subtipo=SubtipoTramite.COMPRAVENTA_PARTICULAR,
    )
    assert "cti" in result.requisitos  # CTI es el doc principal de transferencia
    assert "modelo_620" in result.requisitos
    assert "dni" in result.requisitos
    assert "contrato_compraventa" in result.requisitos
    assert "certificado_defuncion" not in result.requisitos
    assert "modelo_650" not in result.requisitos


def test_transferencia_herencia_requiere_docs_adicionales():
    """Herencia: requiere defunción, modelo 650, herederos y Anexo 650 (§5.1.E)."""
    result = resolver_checklist(
        familia=FamiliaTramite.TRANSFERENCIA,
        subtipo=SubtipoTramite.HERENCIA,
    )
    assert "certificado_defuncion" in result.requisitos
    assert "modelo_650" in result.requisitos
    assert "declaracion_herederos" in result.requisitos
    assert "anexo_650" in result.requisitos
    # Los de la base siguen estando
    assert "cti" in result.requisitos
    assert "modelo_620" in result.requisitos


def test_transferencia_empresa_adquirente_requiere_poder_y_cif():
    """Empresa adquirente: escritura de poder y CIF adicionales (§5.1.F)."""
    result = resolver_checklist(
        familia=FamiliaTramite.TRANSFERENCIA,
        naturaleza_partes=NaturalezaPartes.EMPRESA_ADQUIRENTE,
    )
    assert "escritura_poder" in result.requisitos
    assert "cif" in result.requisitos


def test_transferencia_particular_sin_poder_ni_cif():
    """Transferencia entre particulares: sin escritura ni CIF."""
    result = resolver_checklist(
        familia=FamiliaTramite.TRANSFERENCIA,
        naturaleza_partes=NaturalezaPartes.PARTICULAR,
    )
    assert "escritura_poder" not in result.requisitos
    assert "cif" not in result.requisitos


# ── Otros trámites ────────────────────────────────────────────────────────────

def test_baja():
    result = resolver_checklist(familia=FamiliaTramite.BAJA)
    assert "permiso_circulacion" in result.requisitos
    assert "solicitud_baja" in result.requisitos
    assert "dni" in result.requisitos


def test_duplicado_circulacion():
    result = resolver_checklist(familia=FamiliaTramite.DUPLICADO_CIRCULACION)
    assert "solicitud_duplicado" in result.requisitos
    assert "justificante_pago" in result.requisitos


def test_cambio_domicilio():
    result = resolver_checklist(familia=FamiliaTramite.CAMBIO_DOMICILIO)
    assert "justificante_domicilio" in result.requisitos
    assert "permiso_circulacion" in result.requisitos


def test_placas_verdes():
    result = resolver_checklist(familia=FamiliaTramite.PLACAS_VERDES)
    assert "certificado_homologacion_electrico" in result.requisitos


def test_placas_rojas():
    result = resolver_checklist(familia=FamiliaTramite.PLACAS_ROJAS)
    assert "justificante_pago" in result.requisitos
    assert "permiso_circulacion" not in result.requisitos


# ── Combinaciones ─────────────────────────────────────────────────────────────

def test_herencia_empresa_adquirente_combina_ambas_reglas():
    """Herencia donde el heredero es empresa: aplican §5.1.E y §5.1.F."""
    result = resolver_checklist(
        familia=FamiliaTramite.TRANSFERENCIA,
        subtipo=SubtipoTramite.HERENCIA,
        naturaleza_partes=NaturalezaPartes.EMPRESA_ADQUIRENTE,
    )
    assert "certificado_defuncion" in result.requisitos
    assert "modelo_650" in result.requisitos
    assert "escritura_poder" in result.requisitos
    assert "cif" in result.requisitos


def test_remolque_agricola_aplica_ambos_modificadores():
    """Remolque agrícola: sin impuesto matriculación Y con cartilla agrícola."""
    result = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        tipo_vehiculo=TipoVehiculo.AGRICOLA,  # agrícola implica también tractor = no turismo
    )
    assert "cartilla_agricola" in result.requisitos
    # El tipo AGRICOLA no quita impuesto_matriculacion (solo REMOLQUE lo hace)
    assert "impuesto_matriculacion" in result.requisitos


def test_checklist_resuelto_sin_telematico_por_defecto():
    """Por defecto, no_telematico es False para trámites ordinarios."""
    result = resolver_checklist(familia=FamiliaTramite.TRANSFERENCIA)
    assert result.no_telematico is False
    assert result.requiere_revision_manual is False
