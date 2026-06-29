"""Tests de ingesta de hoja de caja (SAGE)."""
from app.services.ingesta_hoja_caja import (
    parse_hoja_caja_csv, MAPA_CAJA_A_FAMILIA, clasificar_concepto,
)


def _csv():
    return (
        "fecha,concepto,importe,nif,matricula,num_presentacion\n"
        "01/06/2026,TRANSFERENCIA vehiculo,99.00,12345678A,1234ABC,00008\n"
        "01/06/2026,MATRICULACION,150.50,87654321B,5678DEF,00003\n"
    )


def test_parse_hoja_caja_csv_basico():
    hoja = parse_hoja_caja_csv(_csv())
    assert len(hoja.lineas) == 2
    l = hoja.lineas[0]
    assert l.concepto == "TRANSFERENCIA vehiculo"
    assert l.importe == 99.00
    assert l.nif == "12345678A"
    assert l.matricula == "1234ABC"
    assert l.num_presentacion == "00008"


def test_hoja_caja_total():
    hoja = parse_hoja_caja_csv(_csv())
    assert hoja.total == 249.50


def test_buscar_por_matricula():
    hoja = parse_hoja_caja_csv(_csv())
    res = hoja.buscar_por_matricula("1234ABC")
    assert len(res) == 1
    assert res[0].importe == 99.00


def test_mapa_caja_a_familia():
    assert MAPA_CAJA_A_FAMILIA["TRANSFERENCIA"] == "TRANSFERENCIA"
    assert clasificar_concepto("TRANSFERENCIA vehiculo") == "TRANSFERENCIA"
    assert clasificar_concepto("MATRICULACION nueva") == "MATRICULACION"
