"""Tests para aviso_templates.py."""
from app.services.aviso_templates import aviso_1, aviso_2, escalado_admin


def test_aviso_1_contiene_matricula():
    asunto, html, texto = aviso_1("1234 ABC", "Gestoría Test", ["cti", "modelo_620"], [])
    assert "1234 ABC" in asunto
    assert "1234 ABC" in html
    assert "1234 ABC" in texto


def test_aviso_1_lista_requisitos():
    _, html, texto = aviso_1("5678 DEF", "G. Norte", ["cti"], ["modelo_620"])
    assert "Cti" in html or "cti" in html
    assert "Modelo 620" in html or "modelo_620" in html


def test_aviso_1_retorna_tres_strings_no_vacios():
    result = aviso_1("9999 ZZZ", "Gestoría", ["dni"], [])
    assert len(result) == 3
    for s in result:
        assert isinstance(s, str) and len(s) > 0


def test_aviso_2_contiene_matricula_y_gestoria():
    asunto, html, texto = aviso_2("4444 GHI", "Gestoría Sur", ["solicitud_baja"])
    assert "4444 GHI" in asunto
    assert "Gestoría Sur" in html
    assert "4444 GHI" in texto


def test_aviso_2_retorna_tres_strings_no_vacios():
    result = aviso_2("1111 AAA", "G.", ["dni"])
    assert all(isinstance(s, str) and s for s in result)


def test_escalado_admin_contiene_tramite_id():
    asunto, html, texto = escalado_admin("7777 XYZ", "G. Este", "t-escalado-001", ["cti"])
    assert "7777 XYZ" in asunto
    assert "t-escalado-001" in html
    assert "7777 XYZ" in texto


def test_escalado_admin_retorna_tres_strings_no_vacios():
    result = escalado_admin("2222 BBB", "G.", "t-001", ["modelo_620"])
    assert all(isinstance(s, str) and s for s in result)


def test_aviso_1_incluye_seccion_evidencia_con_detalle():
    """aviso_1 con requisitos_evidencia_detalle → sección separada con campos faltantes."""
    _, html, texto = aviso_1(
        matricula="3333 EVI",
        gestoria="G. Sur",
        requisitos_faltantes=[],
        requisitos_evidencia=["anexo_650"],
        requisitos_evidencia_detalle={"anexo_650": ["matricula", "bastidor", "valor_vehiculo"]},
    )
    # La sección de evidencia debe aparecer
    assert "incompleta" in html.lower() or "reenvío" in html.lower()
    assert "matricula" in html or "bastidor" in html
    assert "3333 EVI" in html
    # En texto plano también
    assert "incompleta" in texto.lower() or "reenvío" in texto.lower()


def test_aviso_1_sin_evidencia_no_incluye_seccion_extra():
    """aviso_1 sin evidencia no muestra la sección extra."""
    _, html, texto = aviso_1(
        matricula="4444 NOE",
        gestoria="G. Norte",
        requisitos_faltantes=["cti"],
        requisitos_evidencia=[],
    )
    assert "incompleta" not in html.lower()
    assert "reenvío" not in html.lower()
