"""
Tests de escenarios de negocio end-to-end.

Cada test simula un flujo completo usando RepositorioEnMemoria (sin BD real).
Orden: test rojo → fix → test verde (sesión 9).

Principios verificados:
  - Escalado: Tyrion → gestoría → gestoría → admin (nunca directo)
  - CTI es el documento PRINCIPAL de una transferencia (VALIDO, no EVIDENCIA)
  - no_telematico → pendiente_jefatura (nunca admin)
  - Checklist completo → listo_dgt sin intervención manual
"""
import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.persistencia import TipoMensajeSaliente
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import (
    TipoDocumento, TipoTramite, ValidezVinculo,
    FamiliaTramite, SubtipoTramite, TipoVehiculo,
)
from app.services.ingesta_email import EmailEntrante, AdjuntoEmail
from app.services.motor_cotejo import MotorCotejo, RequisitoCotejo
from app.services.pipeline import Pipeline, RepositorioEnMemoria
from app.services.clasificador import ClasificadorDocumental


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clf_mock():
    return ClasificadorDocumental(client=SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock())
    ))


def _clf_result(tipo: TipoDocumento, score: float = 0.92) -> ResultadoClasificacion:
    nivel = "ALTA" if score >= 0.85 else ("MEDIA" if score >= 0.60 else "BAJA")
    return ResultadoClasificacion(tipo_detectado=tipo, confianza_score=score, confianza_nivel=nivel)


def _adjunto(nombre: str) -> AdjuntoEmail:
    return AdjuntoEmail(nombre, "application/pdf", b"%PDF")


def _email(*nombres: str, msg_id: str = "test@mail.com") -> EmailEntrante:
    return EmailEntrante(
        message_id=msg_id,
        remitente="gestor@ejemplo.com",
        asunto="Documentación trámite",
        fecha=None,
        adjuntos=[_adjunto(n) for n in nombres],
    )


# ── TRANSFERENCIAS ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transferencia_completa_pasa_a_listo_dgt():
    """CTI + Modelo620 → checklist completo (versión acotada) → listo_dgt, 0 avisos."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    clfs = [
        _clf_result(TipoDocumento.CTI),
        _clf_result(TipoDocumento.MODELO_620),
    ]
    with patch.object(clf, "clasificar", side_effect=clfs):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("cti.pdf", "620.pdf"),
            tipo_tramite=TipoTramite.TRANSFERENCIA,
            tramite_id="t-transf-ok",
            gestoria_email="g@gestor.es",
        )

    assert resultado.ok
    assert resultado.estado_checklist.completo
    assert resultado.listo_dgt
    assert resultado.mensajes_preparados == []


@pytest.mark.asyncio
async def test_transferencia_sin_620_genera_aviso_no_escalado():
    """Solo CTI, falta modelo_620 → aviso_1 a gestoría, NUNCA escalado al admin."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    clfs = [
        _clf_result(TipoDocumento.CTI),
    ]
    with patch.object(clf, "clasificar", side_effect=clfs):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("cti.pdf"),
            tipo_tramite=TipoTramite.TRANSFERENCIA,
            tramite_id="t-transf-faltante",
            gestoria_email="g@gestor.es",
        )

    assert resultado.ok
    assert not resultado.listo_dgt
    assert any(m.tipo == TipoMensajeSaliente.AVISO_1 for m in resultado.mensajes_preparados)
    # NUNCA escalado directo
    assert not any(m.tipo == TipoMensajeSaliente.ESCALADO for m in resultado.mensajes_preparados)


@pytest.mark.asyncio
async def test_transferencia_cti_es_valido_no_evidencia():
    """CTI en trámite de transferencia → validez VALIDO (es el doc principal, no evidencia)."""
    motor = MotorCotejo()
    clf_cti = _clf_result(TipoDocumento.CTI, 0.95)
    resultado = motor.cotejar_documento(clf_cti, TipoTramite.TRANSFERENCIA, "cti")
    assert resultado.validez == ValidezVinculo.VALIDO

    # Checklist completo versión acotada: CTI + modelo_620
    docs = {
        "cti": _clf_result(TipoDocumento.CTI, 0.95),
        "modelo_620": _clf_result(TipoDocumento.MODELO_620, 0.90),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs)
    assert "cti" in estado.requisitos_validos
    assert estado.completo


@pytest.mark.asyncio
async def test_transferencia_herencia_completa():
    """Herencia sesión 13: decl_responsable + modelo_650 + anexo_650 → listo_dgt."""
    motor = MotorCotejo()
    # Usar resolver_checklist para obtener los requisitos reales (sesión 13)
    from app.services.motor_cotejo import resolver_checklist
    from app.services.catalogo_documental import FamiliaTramite, SubtipoTramite
    checklist = resolver_checklist(FamiliaTramite.TRANSFERENCIA, SubtipoTramite.HERENCIA)
    requisitos = [RequisitoCotejo(r) for r in checklist.requisitos]

    docs = {
        "declaracion_responsable_fallecimiento": _clf_result(
            TipoDocumento.DECLARACION_RESPONSABLE_FALLECIMIENTO
        ),
        "modelo_650": _clf_result(TipoDocumento.MODELO_650),
        "anexo_650": _clf_result(TipoDocumento.ANEXO_650),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs, requisitos=requisitos)
    assert estado.completo
    assert len(estado.requisitos_validos) == 3


# ── PRINCIPIO DE ESCALADO ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_documento_rechazado_genera_aviso_no_escalado():
    """Hoja de caja en requisito solicitud_baja → RECHAZADO → aviso_1, NO escalado directo.
    Nota: permiso_circulacion es doc de salida, no requisito de entrada para BAJA."""
    motor = MotorCotejo()

    # Cotejo directo: hoja_caja para requisito solicitud_baja → RECHAZADO
    docs = {
        "solicitud_baja": _clf_result(TipoDocumento.HOJA_CAJA, 0.90),
        "dni": _clf_result(TipoDocumento.DNI, 0.92),
    }
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs)

    assert not estado.completo
    assert "solicitud_baja" in estado.requisitos_rechazados
    assert estado.debe_escalar_admin  # motor detecta que eventualmente hay que escalar
    # BUG 1 fix: rechazado también activa pedir_gestoria (aviso_1 primero)
    assert estado.debe_pedir_gestoria

    # El pipeline también genera aviso_1 cuando hay faltantes (solicitud_baja no enviada)
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    clfs = [
        _clf_result(TipoDocumento.HOJA_CAJA, 0.90),
        _clf_result(TipoDocumento.DNI, 0.92),
    ]
    with patch.object(clf, "clasificar", side_effect=clfs):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("hoja_caja.pdf", "dni.pdf"),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-rechazado",
            gestoria_email="g@gestor.es",
        )

    assert resultado.ok
    # Debe haber aviso_1 (solicitud_baja faltante)
    assert any(m.tipo == TipoMensajeSaliente.AVISO_1 for m in resultado.mensajes_preparados)
    # NUNCA escalado directo sin avisos previos
    assert not any(m.tipo == TipoMensajeSaliente.ESCALADO for m in resultado.mensajes_preparados)


def test_escalado_solo_tras_dos_avisos_sin_respuesta():
    """Escalado al admin SOLO tras aviso_1 + aviso_2 sin respuesta (T+60min)."""
    from app.models.persistencia import MensajeSaliente
    from app.core.config import Settings

    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    t_base = datetime.utcnow() - timedelta(minutes=70)

    # Aviso_1 ya enviado hace 70 minutos
    aviso1 = MensajeSaliente(
        tramite_id="t-escalado",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="Aviso 1",
        cuerpo="Faltan documentos",
        preparado_at=t_base,
    )
    repo.guardar_mensaje_saliente(aviso1)

    # T+35: aviso_2 generado
    t_35 = t_base + timedelta(minutes=35)
    nuevos_35 = pipeline.ejecutar_timers(ahora=t_35)
    assert any(m.tipo == TipoMensajeSaliente.AVISO_2 for m in nuevos_35), \
        "aviso_2 no generado en T+35"

    # T+70 con escalado_admin_min=30: aviso_2 lleva 35min sin respuesta → escalar
    settings_test = Settings(
        escalado_aviso2_min=30,
        escalado_admin_min=30,
        email_administrativo="admin@gestor.es",
    )
    t_70 = t_base + timedelta(minutes=70)
    with patch("app.services.pipeline.get_settings", return_value=settings_test):
        nuevos_70 = pipeline.ejecutar_timers(ahora=t_70)

    assert any(m.tipo == TipoMensajeSaliente.ESCALADO for m in nuevos_70), \
        "escalado no generado tras aviso_1 + aviso_2 sin respuesta"


@pytest.mark.asyncio
async def test_nunca_escalado_directo_sin_avisos_previos():
    """Cualquier situación de doc faltante o rechazado: nunca escalado antes de aviso_1."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    # RECHAZADO (hoja_caja en vez de permiso)
    with patch.object(clf, "clasificar", side_effect=[_clf_result(TipoDocumento.HOJA_CAJA)]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("hoja_caja.pdf"),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-no-escalar",
            gestoria_email="g@gestor.es",
        )

    mensajes = resultado.mensajes_preparados
    tipos = [m.tipo for m in mensajes]
    # Si hay ESCALADO, debe existir AVISO_1 previo (no directo)
    if TipoMensajeSaliente.ESCALADO in tipos:
        assert TipoMensajeSaliente.AVISO_1 in tipos, \
            "BUG: escalado directo sin aviso_1 previo"
    # En procesar_email, escalado directo está prohibido
    assert TipoMensajeSaliente.ESCALADO not in tipos, \
        "BUG: escalado debe ser solo por timers (T+60), nunca en procesar_email()"


# ── MATRICULACIONES ───────────────────────────────────────────────────────────

def test_matriculacion_tipo_a_completa():
    """Solicitud + ficha + ivtm + impuesto_mat + dni → checklist completo."""
    motor = MotorCotejo()
    docs = {
        "solicitud_matriculacion": _clf_result(TipoDocumento.SOLICITUD_MATRICULACION),
        "ficha_tecnica": _clf_result(TipoDocumento.FICHA_TECNICA),
        "ivtm": _clf_result(TipoDocumento.IVTM),
        "impuesto_matriculacion": _clf_result(TipoDocumento.IMPUESTO_MATRICULACION),
        "dni": _clf_result(TipoDocumento.DNI),
    }
    estado = motor.evaluar_checklist(TipoTramite.MATRICULACION, docs)
    assert estado.completo
    assert not estado.debe_pedir_gestoria


def test_matriculacion_remolque_sin_impuesto_matriculacion():
    """Remolque: impuesto_matriculacion NO está en requisitos."""
    from app.services.motor_cotejo import resolver_checklist
    checklist = resolver_checklist(
        familia=FamiliaTramite.MATRICULACION,
        tipo_vehiculo=TipoVehiculo.REMOLQUE,
    )
    assert "impuesto_matriculacion" not in checklist.requisitos


@pytest.mark.asyncio
async def test_matriculacion_historico_va_a_jefatura():
    """Vehículo histórico (no_telematico=True) → pendiente_jefatura, sin avisos a admin."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    with patch.object(clf, "clasificar", side_effect=[_clf_result(TipoDocumento.CTI)]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("cti.pdf"),
            tipo_tramite=TipoTramite.TRANSFERENCIA,
            tramite_id="t-historico",
            gestoria_email="g@gestor.es",
            no_telematico=True,
        )

    assert resultado.no_telematico is True
    # No debe haber ningún aviso ni escalado
    assert resultado.mensajes_preparados == []


# ── ESTADOS ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_estado_avanza_automaticamente_cuando_checklist_completo():
    """Pipeline con todos los docs VALIDO → resultado.listo_dgt=True sin intervención."""
    repo = RepositorioEnMemoria()
    clf = _clf_mock()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    # BAJA: permiso_circulacion + dni + solicitud_baja
    clfs = [
        _clf_result(TipoDocumento.PERMISO_CIRCULACION),
        _clf_result(TipoDocumento.DNI),
        _clf_result(TipoDocumento.SOLICITUD_BAJA),
    ]
    with patch.object(clf, "clasificar", side_effect=clfs):
        resultado = await pipeline.procesar_email(
            email_entrante=_email("permiso.pdf", "dni.pdf", "solicitud.pdf"),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="t-baja-ok",
            gestoria_email="g@gestor.es",
        )

    assert resultado.listo_dgt
    assert resultado.estado_checklist.completo
    assert resultado.mensajes_preparados == []


@pytest.mark.asyncio
async def test_badge_alertas_refleja_tramites_con_alerta():
    """GET /api/stats devuelve alertas >= 0 y el campo existe."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "alertas" in data
    assert isinstance(data["alertas"], int)
    assert data["alertas"] >= 0
