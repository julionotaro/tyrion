"""Tests de ingesta de planilla (CSV + campo num_presentacion)."""
from app.services.ingesta_planilla import (
    TramitePlanificado, parse_relacion_transmisiones, parse_relacion_matriculas,
    TipoPlanilla,
)


def test_parse_planilla_csv_transmisiones():
    csv = (
        "num_presentacion,matricula,tasa,adq_nif,razon_social,nombre,tipo_transmision\n"
        "00008,1234ABC,99.00,12345678A,,Juan Pérez,COMPRAVENTA\n"
        "00008,5678DEF,99.00,87654321B,,Ana López,COMPRAVENTA\n"
    )
    planilla = parse_relacion_transmisiones(csv)
    assert planilla.tipo == TipoPlanilla.TRANSMISIONES
    assert len(planilla) == 2
    assert planilla.tramites[0].matricula == "1234ABC"
    assert planilla.tramites[0].tipo_tramite == "TRANSFERENCIA"


def test_parse_planilla_csv_matriculas():
    csv = (
        "num_presentacion,matricula,bastidor,apellido1,apellido2,nombre,fecha\n"
        "00003,1234ABC,WVW12345678901234,Pérez,García,Juan,01/06/2026\n"
    )
    planilla = parse_relacion_matriculas(csv)
    assert planilla.tipo == TipoPlanilla.MATRICULAS
    assert len(planilla) == 1
    assert planilla.tramites[0].bastidor == "WVW12345678901234"
    assert planilla.tramites[0].tipo_tramite == "MATRICULACION"


def test_tramite_planificado_tiene_num_presentacion():
    t = TramitePlanificado(matricula="1234ABC", num_presentacion="00008")
    assert t.num_presentacion == "00008"
