"""Tests for watcher_planilla.py — CSV file detection and ingestion."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.watcher_planilla import procesar_archivo

CSV_TRANSMISIONES = """num_presentacion,matricula,tasa,adq_nif,razon_social,nombre_adquirente,tipo_transmision
EXP-001,1234ABC,110.50,12345678A,,Juan García,compraventa
EXP-002,5678DEF,95.00,87654321B,,Ana Martín,compraventa
"""

CSV_MATRICULAS = """num_presentacion,matricula,bastidor,apellido1,apellido2,nombre,fecha_presentacion
EXP-101,3456JKL,ZFA19800000537243,López,Sanz,María,16/06/2026
"""


def test_procesar_transmisiones(tmp_path):
    (tmp_path / "procesados").mkdir()
    archivo = tmp_path / "transmisiones_hoy.csv"
    archivo.write_text(CSV_TRANSMISIONES, encoding="utf-8")
    n = procesar_archivo(archivo)
    assert n == 2
    assert not archivo.exists()
    assert (tmp_path / "procesados" / "transmisiones_hoy.csv").exists()


def test_procesar_matriculas(tmp_path):
    (tmp_path / "procesados").mkdir()
    archivo = tmp_path / "matriculas_hoy.csv"
    archivo.write_text(CSV_MATRICULAS, encoding="utf-8")
    n = procesar_archivo(archivo)
    assert n == 1
    assert not archivo.exists()


def test_procesar_archivo_desconocido(tmp_path):
    (tmp_path / "procesados").mkdir()
    archivo = tmp_path / "otro_archivo.csv"
    archivo.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
    n = procesar_archivo(archivo)
    assert n == 0


def test_procesar_con_repo(tmp_path):
    (tmp_path / "procesados").mkdir()
    archivo = tmp_path / "transmisiones_test.csv"
    archivo.write_text(CSV_TRANSMISIONES, encoding="utf-8")
    repo = MagicMock()
    repo.guardar_planilla_dia.return_value = "plan-id"
    n = procesar_archivo(archivo, repo=repo)
    assert n == 2
    repo.guardar_planilla_dia.assert_called_once()
    assert repo.guardar_tramite_planificado.call_count == 2
