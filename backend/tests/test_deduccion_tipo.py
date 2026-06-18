"""
Tests para la deducción del tipo de trámite a partir de los documentos.

Principio: el documento PRINCIPAL define el tipo. El administrativo no lo declara.
"""
import pytest

from app.services.catalogo_documental import (
    TipoDocumento, TipoTramite, SubtipoTramite,
)
from app.services.deduccion_tipo import deducir_tipo_tramite


def test_cti_deduce_transferencia():
    """CTI presente → TRANSFERENCIA."""
    r = deducir_tipo_tramite([TipoDocumento.CTI, TipoDocumento.DNI])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.subtipo == SubtipoTramite.NINGUNO
    assert r.documento_principal == "cti"


def test_contrato_deduce_transferencia():
    """Contrato de compraventa sin CTI → TRANSFERENCIA."""
    r = deducir_tipo_tramite([TipoDocumento.CONTRATO_COMPRAVENTA, TipoDocumento.MODELO_620])
    assert r.tipo == TipoTramite.TRANSFERENCIA


def test_solicitud_matriculacion_deduce_matriculacion():
    """Solicitud de matriculación → MATRICULACION."""
    r = deducir_tipo_tramite([
        TipoDocumento.SOLICITUD_MATRICULACION,
        TipoDocumento.FICHA_TECNICA,
    ])
    assert r.tipo == TipoTramite.MATRICULACION
    assert r.documento_principal == "solicitud_matriculacion"


def test_solicitud_baja_deduce_baja():
    """Solicitud de baja → BAJA."""
    r = deducir_tipo_tramite([TipoDocumento.SOLICITUD_BAJA, TipoDocumento.DNI])
    assert r.tipo == TipoTramite.BAJA


def test_cti_con_herencia_deduce_subtipo_herencia():
    """CTI + modelo 650 + declaración herederos → TRANSFERENCIA subtipo herencia."""
    r = deducir_tipo_tramite([
        TipoDocumento.CTI,
        TipoDocumento.MODELO_650,
        TipoDocumento.DECLARACION_HEREDEROS,
        TipoDocumento.CERTIFICADO_DEFUNCION,
    ])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.subtipo == SubtipoTramite.HERENCIA


def test_matriculacion_gana_sobre_secundarios():
    """Si hay solicitud_matriculacion, gana aunque haya otros documentos."""
    r = deducir_tipo_tramite([
        TipoDocumento.DNI,
        TipoDocumento.SOLICITUD_MATRICULACION,
        TipoDocumento.IVTM,
    ])
    assert r.tipo == TipoTramite.MATRICULACION


def test_respaldo_modelo_620_sin_principal():
    """Sin documento principal, modelo 620 sugiere TRANSFERENCIA."""
    r = deducir_tipo_tramite([TipoDocumento.MODELO_620, TipoDocumento.DNI])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.documento_principal is None  # vino por respaldo


def test_respaldo_impuesto_matriculacion():
    """Sin principal, impuesto_matriculacion → MATRICULACION."""
    r = deducir_tipo_tramite([TipoDocumento.IMPUESTO_MATRICULACION, TipoDocumento.DNI])
    assert r.tipo == TipoTramite.MATRICULACION


def test_solo_dni_no_deduce():
    """Solo DNI (ningún documento principal ni de respaldo) → sin deducción."""
    r = deducir_tipo_tramite([TipoDocumento.DNI])
    assert r.tipo is None
    assert not r.deducido


def test_lista_vacia_no_deduce():
    """Sin documentos → no se puede deducir."""
    r = deducir_tipo_tramite([])
    assert r.tipo is None
    assert not r.deducido


def test_cti_prioritario_sobre_contrato():
    """CTI tiene mayor prioridad que contrato (ambos → TRANSFERENCIA igual)."""
    r = deducir_tipo_tramite([TipoDocumento.CONTRATO_COMPRAVENTA, TipoDocumento.CTI])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.documento_principal == "cti"


def test_declaracion_responsable_fallecimiento_sola_deduce_herencia():
    """DECLARACION_RESPONSABLE_FALLECIMIENTO solo → TRANSFERENCIA subtipo herencia."""
    r = deducir_tipo_tramite([TipoDocumento.DECLARACION_RESPONSABLE_FALLECIMIENTO])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.subtipo == SubtipoTramite.HERENCIA
    assert r.documento_principal == "declaracion_responsable_fallecimiento"


def test_declaracion_responsable_prioritaria_sobre_cti():
    """DECLARACION_RESPONSABLE_FALLECIMIENTO tiene prioridad sobre CTI en _PRINCIPALES."""
    r = deducir_tipo_tramite([
        TipoDocumento.CTI,
        TipoDocumento.DECLARACION_RESPONSABLE_FALLECIMIENTO,
    ])
    assert r.documento_principal == "declaracion_responsable_fallecimiento"
    assert r.subtipo == SubtipoTramite.HERENCIA


def test_cti_con_decl_responsable_deduce_herencia():
    """CTI + declaracion_responsable_fallecimiento → TRANSFERENCIA subtipo herencia."""
    r = deducir_tipo_tramite([
        TipoDocumento.DECLARACION_RESPONSABLE_FALLECIMIENTO,
        TipoDocumento.MODELO_650,
        TipoDocumento.ANEXO_650,
    ])
    assert r.tipo == TipoTramite.TRANSFERENCIA
    assert r.subtipo == SubtipoTramite.HERENCIA
