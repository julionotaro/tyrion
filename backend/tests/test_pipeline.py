"""
Tests del pipeline de Tyrion.

Sin API real ni BD: el clasificador y el motor se mockean. Verifica:
  - orquestación adjunto → clasificación → cotejo → avisos
  - aviso_1 automático al detectar faltante (T+0)
  - timers de escalado: aviso_2 (T+30) y escalado al admin (T+60)
  - principio de escalado: gestoría primero, admin ÚLTIMO recurso
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.persistencia import TipoMensajeSaliente
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoDocumento, TipoTramite
from app.services.ingesta_email import AdjuntoEmail, EmailEntrante
from app.services.motor_cotejo import MotorCotejo
from app.services.pipeline import Pipeline, RepositorioEnMemoria


# ---------- helpers ----------

def _email(
    message_id: str = "<test@id>",
    adjuntos: list[AdjuntoEmail] | None = None,
) -> EmailEntrante:
    return EmailEntrante(
        message_id=message_id,
        remitente="gestoria@example.com",
        asunto="Documentos",
        fecha="Mon, 15 Jun 2026 10:00:00 +0000",
        adjuntos=adjuntos or [],
    )


def _adjunto_pdf(nombre: str = "doc.pdf") -> AdjuntoEmail:
    return AdjuntoEmail(nombre=nombre, content_type="application/pdf", contenido=b"%PDF-1.4")


def _clf_mock(tipo: TipoDocumento, score: float = 0.92):
    """Clasificador que siempre devuelve el tipo y score indicados."""
    nivel = "ALTA" if score >= 0.85 else "MEDIA" if score >= 0.60 else "BAJA"
    resultado = ResultadoClasificacion(
        tipo_detectado=tipo,
        confianza_score=score,
        confianza_nivel=nivel,
    )
    cliente = SimpleNamespace()
    cliente.messages = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(
        content=[SimpleNamespace(type="text", text=(
            f'{{"tipo_detectado":"{tipo.value}","confianza_score":{score},'
            f'"datos_extraidos":{{}},"justificacion":"mock"}}'
        ))]
    )))
    from app.services.clasificador import ClasificadorDocumental
    clf = ClasificadorDocumental(client=cliente)
    return clf


def _pipeline_con_motor_real(clf=None) -> tuple[Pipeline, RepositorioEnMemoria]:
    repo = RepositorioEnMemoria()
    from app.services.clasificador import ClasificadorDocumental
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())
    return pipeline, repo


# ---------- procesamiento de emails ----------

@pytest.mark.asyncio
async def test_email_sin_adjuntos_genera_aviso1():
    """Sin adjuntos todos los requisitos faltan → aviso_1 a gestoría automáticamente."""
    pipeline, repo = _pipeline_con_motor_real()
    resultado = await pipeline.procesar_email(
        email_entrante=_email(),
        tipo_tramite=TipoTramite.BAJA,
        tramite_id="tramite-001",
        gestoria_email="g@gestor.es",
    )
    assert resultado.adjuntos_procesados == 0
    # BAJA requiere permiso_circulacion + dni; ninguno llegó → aviso_1
    assert len(resultado.mensajes_preparados) == 1
    assert resultado.mensajes_preparados[0].tipo == TipoMensajeSaliente.AVISO_1


@pytest.mark.asyncio
async def test_adjunto_clasificado_valido_no_genera_aviso(tmp_path):
    """Permiso + DNI completos para BAJA → sin avisos."""
    clf_permiso = _clf_mock(TipoDocumento.PERMISO_CIRCULACION, 0.95)

    repo = RepositorioEnMemoria()

    # Mockeamos el pipeline para que el cotejo reciba docs válidos directamente.
    # Usamos RepositorioEnMemoria + motor real pero inyectamos clasificaciones.
    from app.services.pipeline import Pipeline, _guardar_adjunto_temporal, _limpiar_temporal
    from app.schemas.clasificacion import ResultadoClasificacion

    class PipelineTest(Pipeline):
        """Subclase que parchea _clf.clasificar para devolver tipos fijos por nombre."""
        def __init__(self, mapa_clf, **kw):
            super().__init__(**kw)
            self._mapa = mapa_clf

        async def _clasificar_adjunto(self, nombre, ruta):
            return self._mapa[nombre]

    # Inyectar directamente: mock procesar_email a nivel de clasificaciones
    from unittest.mock import patch, AsyncMock as AM
    from app.services.clasificador import ClasificadorDocumental

    clf = ClasificadorDocumental(client=SimpleNamespace(
        messages=SimpleNamespace(create=AM())
    ))

    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    # Forzar clasificaciones directamente vía patch
    permiso_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.PERMISO_CIRCULACION,
        confianza_score=0.95, confianza_nivel="ALTA",
    )
    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[permiso_clf, dni_clf]):
        adjuntos = [
            _adjunto_pdf("permiso.pdf"),
            _adjunto_pdf("dni.pdf"),
        ]
        resultado = await pipeline.procesar_email(
            email_entrante=_email(adjuntos=adjuntos),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="tramite-002",
            gestoria_email="g@gestor.es",
        )

    assert resultado.adjuntos_procesados == 2
    # BAJA requiere permiso_circulacion + dni → ambos están → sin avisos
    assert resultado.mensajes_preparados == []


@pytest.mark.asyncio
async def test_adjunto_faltante_genera_aviso1():
    """Solo llega el DNI, falta el permiso → aviso_1 automático a gestoría."""
    from app.services.clasificador import ClasificadorDocumental
    from unittest.mock import patch

    clf = ClasificadorDocumental(client=SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock())
    ))
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", return_value=dni_clf):
        resultado = await pipeline.procesar_email(
            email_entrante=_email(adjuntos=[_adjunto_pdf("dni.pdf")]),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="tramite-003",
            gestoria_email="g@gestor.es",
            matricula="1234ABC",
        )

    # Falta permiso_circulacion → aviso_1 preparado
    assert len(resultado.mensajes_preparados) == 1
    msg = resultado.mensajes_preparados[0]
    assert msg.tipo == TipoMensajeSaliente.AVISO_1
    assert msg.destinatario == "g@gestor.es"
    assert "permiso_circulacion" in msg.cuerpo
    assert "1234ABC" in msg.cuerpo


@pytest.mark.asyncio
async def test_evidencia_compatible_genera_aviso1_no_escalado():
    """CTI en lugar de permiso → EVIDENCIA_COMPATIBLE → aviso_1 a gestoría, NO al admin."""
    from app.services.clasificador import ClasificadorDocumental
    from unittest.mock import patch

    clf = ClasificadorDocumental(client=SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock())
    ))
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, clasificador=clf, motor=MotorCotejo())

    cti_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.CTI,
        confianza_score=0.91, confianza_nivel="ALTA",
    )
    dni_clf = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.DNI,
        confianza_score=0.93, confianza_nivel="ALTA",
    )

    with patch.object(clf, "clasificar", side_effect=[cti_clf, dni_clf]):
        resultado = await pipeline.procesar_email(
            email_entrante=_email(adjuntos=[_adjunto_pdf("cti.pdf"), _adjunto_pdf("dni.pdf")]),
            tipo_tramite=TipoTramite.BAJA,
            tramite_id="tramite-004",
            gestoria_email="g@gestor.es",
        )

    tipos = [m.tipo for m in resultado.mensajes_preparados]
    assert TipoMensajeSaliente.AVISO_1 in tipos
    assert TipoMensajeSaliente.ESCALADO not in tipos  # admin es último recurso


# ---------- timers de escalado ----------

def test_timer_aviso2_se_dispara_a_t30():
    """Pasados 30 minutos sin respuesta al aviso_1 → aviso_2 a gestoría."""
    from app.models.persistencia import MensajeSaliente
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, motor=MotorCotejo())

    hace_35 = datetime.utcnow() - timedelta(minutes=35)
    repo._mensajes.append(MensajeSaliente(
        tramite_id="t-005",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="aviso",
        cuerpo="falta doc",
        preparado_at=hace_35,
        enviado=False,
    ))

    nuevos = pipeline.ejecutar_timers()
    assert len(nuevos) == 1
    assert nuevos[0].tipo == TipoMensajeSaliente.AVISO_2
    assert nuevos[0].destinatario == "g@gestor.es"


def test_timer_aviso2_no_se_dispara_antes_de_t30():
    """Con solo 10 minutos no se dispara el aviso_2."""
    from app.models.persistencia import MensajeSaliente
    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, motor=MotorCotejo())

    hace_10 = datetime.utcnow() - timedelta(minutes=10)
    repo._mensajes.append(MensajeSaliente(
        tramite_id="t-006",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="aviso",
        cuerpo="falta doc",
        preparado_at=hace_10,
        enviado=False,
    ))

    nuevos = pipeline.ejecutar_timers()
    assert nuevos == []


def test_timer_escalado_a_admin_a_t60(monkeypatch):
    """Pasados 60 min sin respuesta al aviso_2 → escalado al admin (último recurso)."""
    from app.models.persistencia import MensajeSaliente
    from app.core.config import get_settings, Settings

    # Inyectar email_administrativo para que el timer pueda escalar
    monkeypatch.setattr(
        "app.services.pipeline.get_settings",
        lambda: Settings(email_administrativo="admin@colegio.es"),
    )

    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, motor=MotorCotejo())

    hace_65 = datetime.utcnow() - timedelta(minutes=65)
    repo._mensajes.append(MensajeSaliente(
        tramite_id="t-007",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_2,
        asunto="recordatorio",
        cuerpo="segunda llamada",
        preparado_at=hace_65,
        enviado=False,
    ))

    nuevos = pipeline.ejecutar_timers()
    assert len(nuevos) == 1
    assert nuevos[0].tipo == TipoMensajeSaliente.ESCALADO
    assert nuevos[0].destinatario == "admin@colegio.es"


def test_timer_escalado_no_ocurre_sin_email_admin():
    """Sin email_administrativo configurado, el escalado no se prepara."""
    from app.models.persistencia import MensajeSaliente

    repo = RepositorioEnMemoria()
    pipeline = Pipeline(repo=repo, motor=MotorCotejo())

    hace_65 = datetime.utcnow() - timedelta(minutes=65)
    repo._mensajes.append(MensajeSaliente(
        tramite_id="t-008",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_2,
        asunto="recordatorio",
        cuerpo="segunda llamada",
        preparado_at=hace_65,
        enviado=False,
    ))

    nuevos = pipeline.ejecutar_timers()
    assert nuevos == []  # email_administrativo vacío → sin escalado


def test_orden_escalado_gestoria_primero():
    """El repositorio en memoria respeta el orden: aviso_1 antes que escalado."""
    from app.models.persistencia import MensajeSaliente
    from app.core.config import Settings

    repo = RepositorioEnMemoria()

    # Solo hay aviso_1 — el aviso_2 y el escalado no deben aparecer todavía
    hace_10 = datetime.utcnow() - timedelta(minutes=10)
    repo._mensajes.append(MensajeSaliente(
        tramite_id="t-009",
        destinatario="g@gestor.es",
        tipo=TipoMensajeSaliente.AVISO_1,
        asunto="aviso",
        cuerpo="falta doc",
        preparado_at=hace_10,
        enviado=False,
    ))

    pipeline = Pipeline(repo=repo, motor=MotorCotejo())
    nuevos = pipeline.ejecutar_timers()

    tipos = [m.tipo for m in nuevos]
    assert TipoMensajeSaliente.AVISO_2 not in tipos
    assert TipoMensajeSaliente.ESCALADO not in tipos
