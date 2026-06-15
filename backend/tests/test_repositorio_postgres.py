"""
Tests de integración para RepositorioPostgres.

Se saltan automáticamente si no hay BD disponible (USE_DATOS_PRUEBA=true
o DATABASE_URL no alcanzable). Correr en local o con docker-compose:

    pytest tests/test_repositorio_postgres.py -v -m integration

Para incluirlos en CI, exponer la BD y setear USE_DATOS_PRUEBA=false.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from app.models.persistencia import (
    EmailProcesado,
    EstadoEmail,
    MensajeSaliente,
    TipoMensajeSaliente,
)


# ------------------------------------------------------------------ #
# Fixture: salta si no hay BD disponible                              #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def repo():
    """Devuelve un RepositorioPostgres o salta el módulo si no hay BD."""
    try:
        from app.repositories.repositorio_postgres import RepositorioPostgres
        r = RepositorioPostgres()
        # Test rápido de conectividad
        r.mensaje_ids_procesados()
        return r
    except Exception as exc:
        pytest.skip(f"BD no disponible: {exc}")


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #

@pytest.mark.integration
def test_guardar_y_recuperar_email_procesado(repo):
    message_id = f"test-{datetime.utcnow().isoformat()}@tyrion"
    ep = EmailProcesado(
        message_id=message_id,
        remitente="gestor@ejemplo.com",
        asunto="Documentación trámite T-999",
        fecha_recibido=datetime.utcnow(),
        num_adjuntos=2,
        estado=EstadoEmail.PROCESADO,
    )
    repo.guardar_email_procesado(ep)
    ids = repo.mensaje_ids_procesados()
    assert message_id in ids


@pytest.mark.integration
def test_email_ya_procesado(repo):
    message_id = f"dup-{datetime.utcnow().isoformat()}@tyrion"
    ep = EmailProcesado(
        message_id=message_id,
        remitente="x@x.com",
        asunto="dup",
        fecha_recibido=datetime.utcnow(),
        num_adjuntos=0,
        estado=EstadoEmail.PROCESADO,
    )
    repo.guardar_email_procesado(ep)
    assert repo.email_ya_procesado(message_id) is True
    assert repo.email_ya_procesado("no-existe@tyrion") is False


@pytest.mark.integration
def test_guardar_mensaje_saliente(repo):
    tramite_id = f"T-INT-{datetime.utcnow().timestamp():.0f}"
    ms = MensajeSaliente(
        tramite_id=tramite_id,
        destinatario="gestor@ejemplo.com",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="Tyrion — documentación pendiente",
        cuerpo="Faltan: permiso_circulacion",
        preparado_at=datetime.utcnow(),
    )
    repo.guardar_mensaje_saliente(ms)
    pendientes = repo.obtener_mensajes_pendientes(TipoMensajeSaliente.AVISO_1)
    tramite_ids = [m.tramite_id for m in pendientes]
    assert tramite_id in tramite_ids


@pytest.mark.integration
def test_mensajes_pendientes_aviso2_umbral(repo):
    tramite_id = f"T-AV2-{datetime.utcnow().timestamp():.0f}"
    # Guardamos un aviso_1 con 35 minutos de antigüedad
    ms = MensajeSaliente(
        tramite_id=tramite_id,
        destinatario="gestor@ejemplo.com",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="Tyrion — documentación pendiente",
        cuerpo="Faltan: permiso_circulacion",
        preparado_at=datetime.utcnow() - timedelta(minutes=35),
    )
    repo.guardar_mensaje_saliente(ms)

    ahora = datetime.utcnow()
    pendientes = repo.mensajes_pendientes_de_aviso2(ahora)
    tramite_ids = [p[0] for p in pendientes]
    assert tramite_id in tramite_ids


@pytest.mark.integration
def test_upsert_email_procesado_sin_duplicado(repo):
    """Guardar el mismo message_id dos veces no lanza excepción (ON CONFLICT UPDATE)."""
    message_id = f"upsert-{datetime.utcnow().isoformat()}@tyrion"
    ep = EmailProcesado(
        message_id=message_id,
        remitente="x@x.com",
        asunto="upsert",
        fecha_recibido=datetime.utcnow(),
        num_adjuntos=1,
        estado=EstadoEmail.PROCESADO,
    )
    repo.guardar_email_procesado(ep)
    ep.estado = EstadoEmail.ERROR
    ep.error_detalle = "reintento"
    repo.guardar_email_procesado(ep)  # no debe lanzar
    ids = repo.mensaje_ids_procesados()
    assert message_id in ids
