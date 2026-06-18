"""Tests para el módulo de mapeo email → nombre de gestoría."""
import pytest

from app.services.gestorias import nombre_gestoria, EMAIL_A_GESTORIA


def test_mapeo_conocido_jlogistic():
    assert nombre_gestoria("jlogistic3000@gmail.com") == "Gestoría JLogistic"


def test_mapeo_conocido_ruiz():
    assert nombre_gestoria("ruiz@gestorias.es") == "Gestoria Ruiz"


def test_mapeo_conocido_case_insensitive():
    """El mapeo debe funcionar aunque el email venga en mayúsculas."""
    assert nombre_gestoria("RUIZ@gestorias.es") == "Gestoria Ruiz"
    assert nombre_gestoria("Jlogistic3000@Gmail.COM") == "Gestoría JLogistic"


def test_fallback_email_desconocido():
    """Email no mapeado → fallback legible, no el email crudo."""
    result = nombre_gestoria("gestoria.alvarez@correo.es")
    assert "@" not in result, "El fallback no debe incluir el símbolo @"
    assert "alvarez" in result.lower() or "Alvarez" in result


def test_fallback_capitaliza():
    """El fallback capitaliza la parte local del email."""
    result = nombre_gestoria("nueva.gestoria@test.com")
    assert result[0].isupper(), "El fallback debe empezar en mayúscula"


def test_todos_los_mapeados_conocidos():
    """Todos los emails del diccionario deben retornar su valor exacto."""
    for email, nombre in EMAIL_A_GESTORIA.items():
        assert nombre_gestoria(email) == nombre
