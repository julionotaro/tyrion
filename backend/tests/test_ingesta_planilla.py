"""
Tests para ingesta_planilla.py — parse de Relación de Transmisiones y Matrículas.

Sin llamadas a API ni BD: los parsers son funciones puras sobre strings.
"""
from datetime import date

from app.services.ingesta_planilla import (
    EstadoTramitePlanificado,
    TipoPlanilla,
    parse_relacion_transmisiones,
    parse_relacion_matriculas,
    _normalizar_bastidor,
    _normalizar_matricula,
)


# ── Normalización ─────────────────────────────────────────────────────────────

def test_normalizar_bastidor_mayusculas():
    assert _normalizar_bastidor("vs6rfd000x1234") == "VS6RFD000X1234"


def test_normalizar_bastidor_sin_espacios():
    assert _normalizar_bastidor("VS6RFD 000X 1234") == "VS6RFD000X1234"


def test_normalizar_bastidor_sin_guiones():
    assert _normalizar_bastidor("VS6-RFD-000X-1234") == "VS6RFD000X1234"


def test_normalizar_matricula():
    assert _normalizar_matricula("1234 abc") == "1234ABC"
    assert _normalizar_matricula("1234-ABC") == "1234ABC"


# ── Relación de Transmisiones ─────────────────────────────────────────────────

CSV_TRANSMISIONES = """num_presentacion,matricula,tasa,adq_nif,razon_social,nombre_adquirente,tipo_transmision
EXP-001,1234ABC,110.50,12345678A,,Juan García López,compraventa
EXP-002,5678DEF,95.00,87654321B,,Ana Martín Pérez,compraventa
EXP-003,9012GHI,200.00,11223344C,Empresa SA,Empresa SA,empresa
"""

def test_parse_transmisiones_tres_filas():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES, fecha=date(2026, 6, 15))
    assert planilla.tipo == TipoPlanilla.TRANSMISIONES
    assert len(planilla.tramites) == 3


def test_parse_transmisiones_tipo_tramite():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES)
    for t in planilla.tramites:
        assert t.tipo_tramite == "TRANSFERENCIA"


def test_parse_transmisiones_expediente():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES)
    assert planilla.tramites[0].num_expediente == "EXP-001"
    assert planilla.tramites[1].num_expediente == "EXP-002"


def test_parse_transmisiones_matricula_normalizada():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES)
    assert planilla.tramites[0].matricula == "1234ABC"


def test_parse_transmisiones_nif():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES)
    assert planilla.tramites[0].nif_adquirente == "12345678A"


def test_parse_transmisiones_estado_inicial():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES)
    for t in planilla.tramites:
        assert t.estado == EstadoTramitePlanificado.SIN_DOCUMENTACION


def test_parse_transmisiones_sin_cabecera():
    """También funciona sin cabecera (primera fila = datos)."""
    csv_sin_cab = "EXP-001,1234ABC,110.50,12345678A,,Juan García,compraventa\n"
    planilla = parse_relacion_transmisiones(csv_sin_cab)
    assert len(planilla.tramites) == 1
    assert planilla.tramites[0].matricula == "1234ABC"


def test_parse_transmisiones_tabulador():
    """Separador tabulador también funciona."""
    tsv = "num_presentacion\tmatricula\ttasa\tadq_nif\trazon_social\tnombre\ttipo\n"
    tsv += "EXP-001\t1234ABC\t110.50\t12345678A\t\tJuan García\tcompraventa\n"
    planilla = parse_relacion_transmisiones(tsv)
    assert len(planilla.tramites) == 1


def test_parse_transmisiones_lineas_vacias_ignoradas():
    csv_con_vacias = CSV_TRANSMISIONES + "\n\n\n"
    planilla = parse_relacion_transmisiones(csv_con_vacias)
    assert len(planilla.tramites) == 3


def test_parse_transmisiones_fecha():
    planilla = parse_relacion_transmisiones(CSV_TRANSMISIONES, fecha=date(2026, 6, 15))
    assert planilla.fecha == date(2026, 6, 15)


# ── Relación de Matrículas ────────────────────────────────────────────────────

CSV_MATRICULAS = """num_presentacion,matricula,bastidor,apellido1,apellido2,nombre,fecha_presentacion
EXP-101,3456JKL,ZFA19800000537243,López,Sanz,María,15/06/2026
EXP-102,7890MNO,VSSZZZ6KZHR123456,Sánchez,Torres,Pedro,15/06/2026
"""

def test_parse_matriculas_dos_filas():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS, fecha=date(2026, 6, 15))
    assert planilla.tipo == TipoPlanilla.MATRICULAS
    assert len(planilla.tramites) == 2


def test_parse_matriculas_tipo_tramite():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    for t in planilla.tramites:
        assert t.tipo_tramite == "MATRICULACION"


def test_parse_matriculas_bastidor_normalizado():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    assert planilla.tramites[0].bastidor == "ZFA19800000537243"


def test_parse_matriculas_bastidor_minusculas_normalizado():
    csv = "EXP-101,3456JKL,zfa19800000537243,López,Sanz,María,15/06/2026\n"
    planilla = parse_relacion_matriculas(csv)
    assert planilla.tramites[0].bastidor == "ZFA19800000537243"


def test_parse_matriculas_bastidor_con_espacios():
    csv = "EXP-101,3456JKL,ZFA198 00000 537243,López,Sanz,María,15/06/2026\n"
    planilla = parse_relacion_matriculas(csv)
    assert planilla.tramites[0].bastidor == "ZFA19800000537243"


def test_parse_matriculas_nombre_titular():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    assert "López" in planilla.tramites[0].nombre_titular
    assert "María" in planilla.tramites[0].nombre_titular


def test_parse_matriculas_estado_inicial():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    for t in planilla.tramites:
        assert t.estado == EstadoTramitePlanificado.SIN_DOCUMENTACION


# ── PlanillaDia: búsquedas ────────────────────────────────────────────────────

def test_buscar_por_bastidor_exacto():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    resultados = planilla.buscar_por_bastidor("ZFA19800000537243")
    assert len(resultados) == 1
    assert resultados[0].matricula == "3456JKL"


def test_buscar_por_bastidor_case_insensitive():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    resultados = planilla.buscar_por_bastidor("zfa19800000537243")
    assert len(resultados) == 1


def test_buscar_por_matricula():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    resultados = planilla.buscar_por_matricula("3456JKL")
    assert len(resultados) == 1


def test_buscar_por_matricula_normalizada():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    resultados = planilla.buscar_por_matricula("3456 jkl")
    assert len(resultados) == 1


def test_buscar_no_encontrado():
    planilla = parse_relacion_matriculas(CSV_MATRICULAS)
    assert planilla.buscar_por_bastidor("XXXXXXXXXXXXXXX99") == []
    assert planilla.buscar_por_matricula("9999ZZZ") == []
