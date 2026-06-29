"""Tests de num_presentacion en el store de gestorías."""
from app.services import gestorias


def test_seed_tiene_num_presentacion():
    g = gestorias.obtener("jlogistic3000@gmail.com")
    assert g is not None
    assert g["num_presentacion"] == "00008"


def test_obtener_por_num_presentacion():
    g = gestorias.obtener_por_num_presentacion("00005")
    assert g is not None
    assert g["email"] == "ruiz@gestorias.es"


def test_obtener_por_num_presentacion_no_existe():
    assert gestorias.obtener_por_num_presentacion("99999") is None
