"""
Tests de control de calidad para los cruces documentales B2-B3.

Verifica:
  - El cruce CET(CTI) = CET(modelo_620) detecta discrepancias (instructivo C.1 / matriz §9.2)
  - El cruce bastidor multi-documento en matriculación (matriz §9.4)
  - El checklist de herencia no incluye contrato_compraventa (B1)

Usa evaluar_completitud_extraccion y CAMPOS_REQUERIDOS para comprobar que los
campos de cruce están presentes en ambos lados.
"""
from app.services.catalogo_documental import (
    TipoDocumento, FamiliaTramite, SubtipoTramite,
    CAMPOS_REQUERIDOS, evaluar_completitud_extraccion,
)
from app.services.motor_cotejo import resolver_checklist


# ── Cruce CET: CTI ↔ modelo_620 (B2+B3) ──────────────────────────────────────

def test_cet_en_campos_requeridos_cti():
    """CTI debe incluir cet en sus campos requeridos (clave de cruce con 620)."""
    assert "cet" in CAMPOS_REQUERIDOS[TipoDocumento.CTI]


def test_cet_en_campos_requeridos_modelo620():
    """modelo_620 debe incluir cet en sus campos requeridos (mismo cruce)."""
    assert "cet" in CAMPOS_REQUERIDOS[TipoDocumento.MODELO_620]


def test_bastidor_en_campos_requeridos_modelo620():
    """modelo_620 debe incluir bastidor (cruce de integridad con CTI — matriz §9.2)."""
    assert "bastidor" in CAMPOS_REQUERIDOS[TipoDocumento.MODELO_620]


def test_cet_consistente_mismos_datos():
    """Dos documentos con mismo CET → ambos completos, cruce OK."""
    datos_cti = {"matricula": "1234ABC", "dni_adquirente": "12345678A", "dni_transmitente": "87654321B", "cet": "CET-001"}
    datos_620 = {"matricula": "1234ABC", "bastidor": "WBA1", "importe": "400",
                 "fecha_devengo": "2026-01-01", "cet": "CET-001",
                 "nif_adquirente": "12345678A", "nif_transmitente": "87654321B"}
    ok_cti, _ = evaluar_completitud_extraccion(TipoDocumento.CTI, datos_cti)
    ok_620, _ = evaluar_completitud_extraccion(TipoDocumento.MODELO_620, datos_620)
    assert ok_cti and ok_620
    # El cruce CET coincide
    assert datos_cti["cet"] == datos_620["cet"]


def test_cet_discrepante_detecta_falta():
    """Si cet falta en uno de los documentos, evaluar_completitud lo señala."""
    datos_sin_cet = {"matricula": "1234ABC", "titular": "Juan", "bastidor": "WBA1"}
    _, faltantes = evaluar_completitud_extraccion(TipoDocumento.CTI, datos_sin_cet)
    assert "cet" in faltantes


# ── Cruce bastidor matriculación (B5+B6) ──────────────────────────────────────

def test_bastidor_en_ficha_tecnica():
    """ficha_tecnica incluye bastidor (cruce matriculación §9.4)."""
    assert "bastidor" in CAMPOS_REQUERIDOS[TipoDocumento.FICHA_TECNICA]


def test_bastidor_en_solicitud_matriculacion():
    """solicitud_matriculacion incluye bastidor (cruce matriculación §9.4)."""
    assert "bastidor" in CAMPOS_REQUERIDOS[TipoDocumento.SOLICITUD_MATRICULACION]


def test_bastidor_en_ivtm():
    """ivtm incluye bastidor (cruce matriculación §9.4)."""
    assert "bastidor" in CAMPOS_REQUERIDOS[TipoDocumento.IVTM]


def test_potencia_kw_en_ficha_tecnica():
    """ficha_tecnica incluye potencia_kw (campo P.2, base de cálculo IVTM)."""
    assert "potencia_kw" in CAMPOS_REQUERIDOS[TipoDocumento.FICHA_TECNICA]


def test_potencia_kw_en_ivtm():
    """ivtm incluye potencia_kw (misma base de cálculo — cruce §9.4)."""
    assert "potencia_kw" in CAMPOS_REQUERIDOS[TipoDocumento.IVTM]


def test_bastidor_cruce_matriculacion_consistente():
    """Bastidor en ficha_tecnica, ivtm y solicitud_matriculacion coincide → cruce OK."""
    bastidor_comun = "WVW12345"
    datos_ficha = {"marca": "VW", "modelo": "Golf", "bastidor": bastidor_comun, "potencia_kw": "85"}
    datos_ivtm = {"matricula": "1234ABC", "importe": "120", "bastidor": bastidor_comun, "potencia_kw": "85"}
    datos_sol = {"matricula": "1234ABC", "titular": "Ana", "bastidor": bastidor_comun}

    for tipo, datos in [
        (TipoDocumento.FICHA_TECNICA, datos_ficha),
        (TipoDocumento.IVTM, datos_ivtm),
        (TipoDocumento.SOLICITUD_MATRICULACION, datos_sol),
    ]:
        ok, faltantes = evaluar_completitud_extraccion(tipo, datos)
        assert ok, f"{tipo.value} incompleto: faltan {faltantes}"
        assert datos["bastidor"] == bastidor_comun


# ── Checklist herencia (B1) ────────────────────────────────────────────────────

def test_checklist_herencia_completo():
    """Herencia: checklist real confirmado sesión 13.

    Doc central: declaracion_responsable_fallecimiento + modelo_650 + anexo_650.
    Sin CTI, DNI, contrato, modelo_620 ni certificado_defuncion en el checklist de cotejo.
    """
    cl = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    reqs = set(cl.requisitos)

    esperados = {"declaracion_responsable_fallecimiento", "modelo_650", "anexo_650"}
    prohibidos = {"contrato_compraventa", "modelo_620", "cti", "dni",
                  "certificado_defuncion", "declaracion_herederos"}

    assert esperados.issubset(reqs), f"Faltan: {esperados - reqs}"
    assert not (prohibidos & reqs), f"No deben estar: {prohibidos & reqs}"
