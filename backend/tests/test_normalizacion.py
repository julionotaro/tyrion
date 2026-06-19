"""Tests para normalización de identificadores."""
import pytest
from app.services.registro_tramites import normalizar_matricula, normalizar_bastidor


def test_matricula_con_espacio():
    assert normalizar_matricula("5042 HZM") == "5042HZM"


def test_matricula_sin_espacio():
    assert normalizar_matricula("5042HZM") == "5042HZM"


def test_matricula_con_guion():
    assert normalizar_matricula("5042-HZM") == "5042HZM"


def test_matricula_minusculas():
    assert normalizar_matricula("5042hzm") == "5042HZM"


def test_matricula_mixta():
    assert normalizar_matricula("5042 - hzm") == "5042HZM"


def test_matricula_none():
    assert normalizar_matricula(None) == ""


def test_matricula_vacia():
    assert normalizar_matricula("") == ""


def test_bastidor_minusculas():
    assert normalizar_bastidor("wba3a5c57df123456") == "WBA3A5C57DF123456"


def test_bastidor_con_espacio():
    assert normalizar_bastidor("WBA3A5C57 DF123456") == "WBA3A5C57DF123456"


def test_todas_las_variantes_igualan():
    """5042HZM, 5042 HZM y 5042-hzm deben normalizar al mismo valor."""
    variantes = ["5042HZM", "5042 HZM", "5042-hzm", "5042 - HZM"]
    normalizadas = [normalizar_matricula(v) for v in variantes]
    assert len(set(normalizadas)) == 1
