"""
Tests para cruce_planilla.py — cruce email↔planilla del día.

Cubre: match exacto bastidor, match 4 dígitos, match matrícula,
match NIF, sin match, múltiples candidatos, planilla vacía.
"""
from datetime import date

from app.services.cruce_planilla import (
    ConfianzaCruce,
    MetodoCruce,
    cruzar_email_con_planilla,
)
from app.services.ingesta_planilla import (
    PlanillaDia,
    TipoPlanilla,
    TramitePlanificado,
)


# ── Fixture: planilla con 3 trámites ─────────────────────────────────────────

def _planilla() -> PlanillaDia:
    return PlanillaDia(
        fecha=date(2026, 6, 15),
        tipo=TipoPlanilla.TRANSMISIONES,
        tramites=[
            TramitePlanificado(
                bastidor="VS6RFD000X1234AB",
                matricula="1234ABC",
                nif_adquirente="12345678A",
                num_expediente="EXP-001",
                nombre_titular="Juan García",
                tipo_tramite="TRANSFERENCIA",
            ),
            TramitePlanificado(
                bastidor="WVWZZZ1KZAW123456",
                matricula="5678DEF",
                nif_adquirente="87654321B",
                num_expediente="EXP-002",
                nombre_titular="Ana Martín",
                tipo_tramite="TRANSFERENCIA",
            ),
            TramitePlanificado(
                bastidor="ZFA19800000537243",
                matricula="9012GHI",
                nif_adquirente="11223344C",
                num_expediente="EXP-003",
                nombre_titular="Carlos Ruiz",
                tipo_tramite="MATRICULACION",
            ),
        ],
    )


# ── Match bastidor exacto ─────────────────────────────────────────────────────

def test_match_bastidor_exacto_confianza_alta():
    resultado = cruzar_email_con_planilla(
        bastidor_email="VS6RFD000X1234AB",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.ALTA
    assert resultado.metodo == MetodoCruce.BASTIDOR_EXACTO
    assert resultado.tramite_planificado.num_expediente == "EXP-001"


def test_match_bastidor_exacto_case_insensitive():
    resultado = cruzar_email_con_planilla(
        bastidor_email="vs6rfd000x1234ab",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.ALTA


def test_match_bastidor_exacto_con_espacios():
    resultado = cruzar_email_con_planilla(
        bastidor_email=" VS6RFD000X1234AB ",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.ALTA


# ── Match 4 últimos dígitos del bastidor ─────────────────────────────────────

def test_match_bastidor_4dig_cuando_no_hay_exacto():
    """Solo los últimos 4 dígitos conocidos: match MEDIA."""
    resultado = cruzar_email_con_planilla(
        bastidor_email="XXXXXXXXXXXX4AB",   # sufijo "4AB" no da 4 digs iguales
        planilla=_planilla(),
    )
    # Sufijo real: "4AB" → 3 chars < 4, sin match de 4 dígitos
    # Probamos con sufijo que sí sea 4 chars
    resultado = cruzar_email_con_planilla(
        bastidor_email="XXXXXXXXXXXX34AB",   # sufijo "34AB"
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.MEDIA
    assert resultado.metodo == MetodoCruce.BASTIDOR_4DIG


def test_match_bastidor_4dig_EXP003():
    """Últimos 4 dígitos de ZFA19800000537243 = '7243'."""
    resultado = cruzar_email_con_planilla(
        bastidor_email="XXXXXXXXXXXXX7243",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.metodo == MetodoCruce.BASTIDOR_4DIG
    assert resultado.tramite_planificado.num_expediente == "EXP-003"


# ── Match matrícula ───────────────────────────────────────────────────────────

def test_match_matricula_cuando_sin_bastidor():
    resultado = cruzar_email_con_planilla(
        matricula_email="5678DEF",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.MEDIA
    assert resultado.metodo == MetodoCruce.MATRICULA
    assert resultado.tramite_planificado.num_expediente == "EXP-002"


def test_match_matricula_normalizada():
    resultado = cruzar_email_con_planilla(
        matricula_email="5678 def",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.metodo == MetodoCruce.MATRICULA


# ── Match NIF ─────────────────────────────────────────────────────────────────

def test_match_nif_baja_confianza():
    resultado = cruzar_email_con_planilla(
        nif_email="11223344C",
        planilla=_planilla(),
    )
    assert resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.BAJA
    assert resultado.metodo == MetodoCruce.NIF
    assert resultado.tramite_planificado.num_expediente == "EXP-003"


def test_match_nif_case_insensitive():
    resultado = cruzar_email_con_planilla(
        nif_email="11223344c",
        planilla=_planilla(),
    )
    assert resultado.tiene_match


# ── Sin match ─────────────────────────────────────────────────────────────────

def test_sin_match_bastidor_desconocido():
    resultado = cruzar_email_con_planilla(
        bastidor_email="XXXXXXXXXXXXXXX99",
        matricula_email="9999ZZZ",
        planilla=_planilla(),
    )
    assert not resultado.tiene_match
    assert resultado.confianza == ConfianzaCruce.NINGUNA
    assert resultado.metodo == MetodoCruce.SIN_MATCH


def test_sin_match_planilla_none():
    resultado = cruzar_email_con_planilla(
        bastidor_email="VS6RFD000X1234AB",
        planilla=None,
    )
    assert not resultado.tiene_match
    assert resultado.metodo == MetodoCruce.SIN_MATCH


def test_sin_match_planilla_vacia():
    planilla_vacia = PlanillaDia(
        fecha=date(2026, 6, 15),
        tipo=TipoPlanilla.TRANSMISIONES,
        tramites=[],
    )
    resultado = cruzar_email_con_planilla(
        bastidor_email="VS6RFD000X1234AB",
        planilla=planilla_vacia,
    )
    assert not resultado.tiene_match


def test_sin_match_sin_datos():
    """Sin ningún dato de búsqueda."""
    resultado = cruzar_email_con_planilla(planilla=_planilla())
    assert not resultado.tiene_match


# ── Múltiples candidatos ──────────────────────────────────────────────────────

def test_multiples_candidatos_mismo_sufijo_ambiguo():
    """Dos trámites con el mismo sufijo de bastidor → ambiguo=True."""
    planilla = PlanillaDia(
        fecha=date(2026, 6, 15),
        tipo=TipoPlanilla.TRANSMISIONES,
        tramites=[
            TramitePlanificado(bastidor="AAAAAAAAAAAA1111", matricula="1111AAA", tipo_tramite="TRANSFERENCIA"),
            TramitePlanificado(bastidor="BBBBBBBBBBBB1111", matricula="2222BBB", tipo_tramite="TRANSFERENCIA"),
        ],
    )
    resultado = cruzar_email_con_planilla(
        bastidor_email="XXXXXXXXXXXX1111",
        planilla=planilla,
    )
    assert resultado.tiene_match
    assert resultado.ambiguo is True
    assert resultado.candidatos == 2
    # Se devuelve el primero
    assert resultado.tramite_planificado.matricula == "1111AAA"


# ── Prioridad de métodos ──────────────────────────────────────────────────────

def test_bastidor_exacto_tiene_prioridad_sobre_matricula():
    """Si hay bastidor exacto, no se usa la matrícula aunque también matchee."""
    resultado = cruzar_email_con_planilla(
        bastidor_email="VS6RFD000X1234AB",  # EXP-001
        matricula_email="5678DEF",           # EXP-002
        planilla=_planilla(),
    )
    assert resultado.metodo == MetodoCruce.BASTIDOR_EXACTO
    assert resultado.tramite_planificado.num_expediente == "EXP-001"
