"""Tests del motor de conciliación diaria."""
from datetime import date

from app.services.conciliacion import conciliar, EstadoConciliacion
from app.services.ingesta_planilla import (
    PlanillaDia, TramitePlanificado, TipoPlanilla,
)
from app.services.ingesta_hoja_caja import parse_hoja_caja_csv


def _planilla(*tramites):
    return PlanillaDia(
        fecha=date(2026, 6, 1),
        tipo=TipoPlanilla.TRANSMISIONES,
        tramites=list(tramites),
    )


def test_conciliar_planilla_sin_expedientes():
    pl = _planilla(
        TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"),
        TramitePlanificado(matricula="5678DEF", tipo_tramite="TRANSFERENCIA"),
    )
    conc = conciliar(pl, expedientes=[])
    assert conc.total == 2
    assert all(f.estado == EstadoConciliacion.SIN_EXPEDIENTE for f in conc.filas)
    assert conc.sin_expediente == 2


def test_conciliar_planilla_con_expediente_pendiente():
    pl = _planilla(TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"))
    exp = {"id": "t1", "matricula": "1234ABC", "estado": "pendiente_gestoria",
           "gestoria": "Ruiz", "gestoria_email": "ruiz@gestorias.es",
           "identificadores": {"matricula": "1234ABC"}}
    conc = conciliar(pl, expedientes=[exp])
    fila = conc.filas[0]
    assert fila.en_expediente is True
    assert fila.estado == EstadoConciliacion.PENDIENTE_DOC
    assert fila.tramite_id == "t1"


def test_conciliar_expediente_resuelto_cuadrado():
    pl = _planilla(TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"))
    exp = {"id": "t1", "matricula": "1234ABC", "estado": "listo_dgt",
           "identificadores": {"matricula": "1234ABC"}}
    conc = conciliar(pl, expedientes=[exp])
    assert conc.filas[0].estado == EstadoConciliacion.CUADRADO
    assert conc.cuadrados == 1


def test_conciliar_detecta_duplicado():
    pl = _planilla(
        TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"),
        TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"),
    )
    conc = conciliar(pl, expedientes=[])
    assert all(f.estado == EstadoConciliacion.DUPLICADO for f in conc.filas)


def test_conciliar_con_caja():
    pl = _planilla(TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"))
    hoja = parse_hoja_caja_csv(
        "fecha,concepto,importe,nif,matricula,num_presentacion\n"
        "01/06/2026,TRANSFERENCIA,99.00,12345678A,1234ABC,00008\n"
    )
    conc = conciliar(pl, expedientes=[], hoja_caja=hoja)
    assert conc.filas[0].en_caja is True
    assert conc.filas[0].importe_caja == 99.00
    assert conc.descuadre_caja is not None
    assert conc.descuadre_caja.total_caja == 99.00


def test_descuadre_caja_lineas_sin_cruce():
    pl = _planilla(TramitePlanificado(matricula="1234ABC", tipo_tramite="TRANSFERENCIA"))
    hoja = parse_hoja_caja_csv(
        "fecha,concepto,importe,nif,matricula,num_presentacion\n"
        "01/06/2026,TRANSFERENCIA,99.00,12345678A,9999ZZZ,00099\n"
    )
    conc = conciliar(pl, expedientes=[], hoja_caja=hoja)
    assert len(conc.descuadre_caja.lineas_sin_cruce) == 1
    assert "1234ABC" in conc.descuadre_caja.planilla_sin_caja
