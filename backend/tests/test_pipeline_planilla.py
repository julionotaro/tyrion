"""
Tests de integración pipeline + planilla:
  - Email con match en planilla → cruce registrado
  - Email sin match → no bloquea, continúa flujo normal
  - Trámite no_telematico → pendiente_jefatura (no escala al admin)
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.persistencia import TipoMensajeSaliente
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento, TipoTramite
from app.services.cruce_planilla import ConfianzaCruce, MetodoCruce
from app.services.ingesta_email import EmailEntrante, AdjuntoEmail
from app.services.ingesta_planilla import (
    PlanillaDia,
    TipoPlanilla,
    TramitePlanificado,
    EstadoTramitePlanificado,
)
from app.services.motor_cotejo import MotorCotejo
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from datetime import date


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_simple(message_id: str = "test@mail.com") -> EmailEntrante:
    return EmailEntrante(
        message_id=message_id,
        remitente="gestor@ejemplo.com",
        asunto="Documentación trámite",
        fecha=None,
        adjuntos=[
            AdjuntoEmail("permiso.pdf", "application/pdf", b"pdf"),
            AdjuntoEmail("solicitud_baja.pdf", "application/pdf", b"pdf"),
            AdjuntoEmail("dni.pdf", "application/pdf", b"pdf"),
        ],
    )


def _planilla_con_tramite(bastidor: str, matricula: str = "") -> PlanillaDia:
    return PlanillaDia(
        fecha=date(2026, 6, 15),
        tipo=TipoPlanilla.TRANSMISIONES,
        tramites=[
            TramitePlanificado(
                bastidor=bastidor,
                matricula=matricula,
                nif_adquirente="12345678A",
                num_expediente="EXP-TEST-001",
                nombre_titular="Test Titular",
                tipo_tramite="BAJA",
            )
        ],
    )


def _clf_mock():
    from app.services.clasificador import ClasificadorDocumental
    return ClasificadorDocumental(client=SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock())
    ))


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_email_con_match_bastidor_registra_cruce():
    """Email cuyo bastidor coincide con la planilla → cruce con confianza ALTA."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    planilla = _planilla_con_tramite("VS6RFD000X1234AB", "1234ABC")
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo(), planilla=planilla)

    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )
    baja_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.SOLICITUD_BAJA,
        confianza_score=0.90, confianza_nivel="ALTA",
    )
    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf, baja_clf, dni_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email_simple(),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-test",
            gestoria_email="g@gestor.es",
            bastidor="VS6RFD000X1234AB",
        )

    assert resultado.cruce_planilla is not None
    assert resultado.cruce_planilla.tiene_match
    assert resultado.cruce_planilla.confianza == ConfianzaCruce.ALTA
    assert resultado.cruce_planilla.metodo == MetodoCruce.BASTIDOR_EXACTO


@pytest.mark.asyncio
async def test_email_sin_match_no_bloquea():
    """Email sin match en planilla → flujo continúa, no_telematico=False, sin error."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    planilla = _planilla_con_tramite("AAAAAAAAAAAAAAAA")  # bastidor distinto
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo(), planilla=planilla)

    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )
    baja_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.SOLICITUD_BAJA,
        confianza_score=0.90, confianza_nivel="ALTA",
    )
    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf, baja_clf, dni_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email_simple("sin-match@mail.com"),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-test-sinmatch",
            gestoria_email="g@gestor.es",
            bastidor="XXXXXXXXXXXXXXX99",
        )

    assert resultado.ok
    assert resultado.cruce_planilla is not None
    assert not resultado.cruce_planilla.tiene_match
    assert resultado.cruce_planilla.metodo == MetodoCruce.SIN_MATCH


@pytest.mark.asyncio
async def test_email_sin_planilla_no_bloquea():
    """Sin planilla cargada → sin_match, flujo normal sin error."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo(), planilla=None)

    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )
    baja_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.SOLICITUD_BAJA,
        confianza_score=0.90, confianza_nivel="ALTA",
    )
    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf, baja_clf, dni_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email_simple(),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-test-noplan",
            gestoria_email="g@gestor.es",
        )

    assert resultado.ok
    assert not resultado.cruce_planilla.tiene_match


@pytest.mark.asyncio
async def test_tramite_no_telematico_no_genera_avisos():
    """Trámite histórico (no_telematico=True): no se escala al admin, no hay avisos."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    # Clasificaciones con un faltante (modelo_620)
    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=EmailEntrante(
                message_id="historico@mail.com",
                remitente="gestor@ejemplo.com",
                asunto="Vehículo histórico",
                fecha=None,
                adjuntos=[AdjuntoEmail("permiso.pdf", "application/pdf", b"pdf")],
            ),
            tipo_tramite=TipoTramite.TRANSFERENCIA,
            tramite_id="t-historico",
            gestoria_email="g@gestor.es",
            no_telematico=True,
        )

    assert resultado.no_telematico is True
    # No debe haber avisos (va a Jefatura, no al admin)
    assert resultado.mensajes_preparados == []


@pytest.mark.asyncio
async def test_tramite_telematico_con_faltante_genera_aviso():
    """Trámite telemático normal con faltante → aviso_1 generado (comportamiento anterior)."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=EmailEntrante(
                message_id="telematico@mail.com",
                remitente="gestor@ejemplo.com",
                asunto="Trámite con faltante",
                fecha=None,
                adjuntos=[AdjuntoEmail("permiso.pdf", "application/pdf", b"pdf")],
            ),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-baja",
            gestoria_email="g@gestor.es",
            no_telematico=False,  # telemático → escalado normal
        )

    # BAJA necesita permiso + dni + solicitud_baja → falta dni y solicitud_baja
    assert any(
        m.tipo == TipoMensajeSaliente.AVISO_1
        for m in resultado.mensajes_preparados
    )
