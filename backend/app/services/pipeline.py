"""
Pipeline automático de Tyrion — orquestación del flujo completo.

Adjunto recibido → clasificador → motor de cotejo → avisos automáticos.

Principio de escalado (CLAUDE.md, principio 3):
  T+0min  → aviso_1 a gestoría (primer aviso automático al detectar faltante)
  T+30min → aviso_2 a gestoría (segundo aviso si no respondió)
  T+60min → escalado al administrativo (ÚLTIMO recurso, nunca el primero)

Principio 4: PREPARADO ≠ ENVIADO. El pipeline deja los mensajes en estado
PREPARADO si no hay integración de envío real. La función `_enviar_mensaje`
es el único punto de integración real: en producción se implementa; en tests
se mockea.

TODO sesión 2:
  - Tiempos reales por tipo de trámite (ahora fijos: 30/60 min desde config)
  - % de docs que llegan mal (métrica para ajustar umbrales)
  - Canal oficial con gestorías (¿Tempus, email o teléfono?)
  - Integración real de envío SMTP (ahora solo PREPARADO)
"""
from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from app.core.config import get_settings
from app.models.persistencia import (
    EmailProcesado,
    EstadoEmail,
    MensajeSaliente,
    TipoMensajeSaliente,
)
from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import TipoTramite
from app.services.clasificador import ClasificadorDocumental
from app.services.ingesta_email import AdjuntoEmail, EmailEntrante
from app.services.motor_cotejo import EstadoChecklist, MotorCotejo

logger = logging.getLogger(__name__)


@dataclass
class ResultadoPipeline:
    """Resultado de procesar un email completo a través del pipeline."""
    email_message_id: str
    adjuntos_procesados: int = 0
    clasificaciones: dict[str, ResultadoClasificacion] = field(default_factory=dict)
    estado_checklist: EstadoChecklist | None = None
    mensajes_preparados: list[MensajeSaliente] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class RepositorioPipeline(Protocol):
    """Abstracción de persistencia para el pipeline. Permite testear sin BD."""

    def guardar_email_procesado(self, ep: EmailProcesado) -> None: ...
    def mensaje_ids_procesados(self) -> set[str]: ...
    def guardar_mensaje_saliente(self, ms: MensajeSaliente) -> None: ...
    def mensajes_pendientes_de_aviso2(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        """Tuplas (tramite_id, destinatario, preparado_at) de aviso_1 sin respuesta."""
        ...
    def mensajes_pendientes_de_escalado(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        """Tuplas (tramite_id, destinatario, preparado_at) de aviso_2 sin respuesta."""
        ...


class RepositorioEnMemoria:
    """Implementación en memoria de RepositorioPipeline — solo para tests."""

    def __init__(self):
        self._emails: dict[str, EmailProcesado] = {}
        self._mensajes: list[MensajeSaliente] = []

    def guardar_email_procesado(self, ep: EmailProcesado) -> None:
        self._emails[ep.message_id] = ep

    def mensaje_ids_procesados(self) -> set[str]:
        return set(self._emails.keys())

    def guardar_mensaje_saliente(self, ms: MensajeSaliente) -> None:
        self._mensajes.append(ms)

    def mensajes_pendientes_de_aviso2(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        s = get_settings()
        umbral = ahora - timedelta(minutes=s.escalado_aviso2_min)
        return [
            (m.tramite_id, m.destinatario, m.preparado_at)
            for m in self._mensajes
            if m.tipo == TipoMensajeSaliente.AVISO_1
            and not m.enviado
            and m.preparado_at <= umbral
        ]

    def mensajes_pendientes_de_escalado(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        s = get_settings()
        umbral = ahora - timedelta(minutes=s.escalado_admin_min)
        return [
            (m.tramite_id, m.destinatario, m.preparado_at)
            for m in self._mensajes
            if m.tipo == TipoMensajeSaliente.AVISO_2
            and not m.enviado
            and m.preparado_at <= umbral
        ]


def _guardar_adjunto_temporal(adjunto: AdjuntoEmail) -> str:
    """Guarda el adjunto en disco temporal y devuelve la ruta."""
    ext = os.path.splitext(adjunto.nombre)[1] or ".bin"
    fd, ruta = tempfile.mkstemp(suffix=ext, prefix="tyrion_")
    os.close(fd)
    with open(ruta, "wb") as f:
        f.write(adjunto.contenido)
    return ruta


def _limpiar_temporal(ruta: str) -> None:
    try:
        os.unlink(ruta)
    except OSError:
        pass


def _preparar_aviso(
    tramite_id: str,
    destinatario: str,
    tipo: TipoMensajeSaliente,
    cuerpo: str,
    matricula: str | None = None,
) -> MensajeSaliente:
    tipo_label = {
        TipoMensajeSaliente.AVISO_1: "documentación pendiente",
        TipoMensajeSaliente.AVISO_2: "recordatorio urgente de documentación",
        TipoMensajeSaliente.ESCALADO: "expediente escalado al administrativo",
    }[tipo]
    matricula_str = f" ({matricula})" if matricula else ""
    return MensajeSaliente(
        tramite_id=tramite_id,
        destinatario=destinatario,
        tipo=tipo,
        asunto=f"Tyrion — {tipo_label}{matricula_str}",
        cuerpo=cuerpo,
    )


class Pipeline:
    """Orquesta el flujo completo: email → clasificador → cotejo → avisos.

    Recibe el clasificador y el motor inyectados para poder testear
    cada capa de forma aislada.
    """

    def __init__(
        self,
        repo: RepositorioPipeline,
        clasificador: ClasificadorDocumental | None = None,
        motor: MotorCotejo | None = None,
    ):
        self._repo = repo
        self._clf = clasificador or ClasificadorDocumental()
        self._motor = motor or MotorCotejo()

    async def procesar_email(
        self,
        email_entrante: EmailEntrante,
        tipo_tramite: TipoTramite,
        tramite_id: str,
        gestoria_email: str,
        matricula: str | None = None,
    ) -> ResultadoPipeline:
        """Procesa un email completo: clasifica adjuntos, coteja, prepara avisos.

        Si falta documentación o hay errores → prepara aviso_1 automáticamente
        (T+0). Los avisos siguientes (aviso_2 y escalado) los dispara
        `ejecutar_timers()`, que debe llamarse periódicamente.
        """
        resultado = ResultadoPipeline(email_message_id=email_entrante.message_id)
        ep = EmailProcesado(
            message_id=email_entrante.message_id,
            remitente=email_entrante.remitente,
            asunto=email_entrante.asunto,
            fecha_recibido=datetime.utcnow(),
            num_adjuntos=len(email_entrante.adjuntos),
            estado=EstadoEmail.RECIBIDO,
        )

        clasificaciones: dict[str, ResultadoClasificacion] = {}

        for adjunto in email_entrante.adjuntos:
            ruta = _guardar_adjunto_temporal(adjunto)
            try:
                clf_resultado = await self._clf.clasificar(ruta)
                # El tipo detectado como clave provisional (el cotejo asignará el requisito)
                clasificaciones[adjunto.nombre] = clf_resultado
                resultado.adjuntos_procesados += 1
            except Exception as exc:
                logger.error("Error clasificando '%s': %s", adjunto.nombre, exc)
                ep.estado = EstadoEmail.ERROR
                ep.error_detalle = str(exc)
            finally:
                _limpiar_temporal(ruta)

        resultado.clasificaciones = clasificaciones

        # Construir mapa requisito → clasificación usando el tipo detectado como clave.
        # En v1 asumimos un adjunto por tipo: la clasificación mapea directamente
        # al requisito del mismo nombre. En sesión 2 se puede refinar con metadata.
        docs_por_requisito = {
            clf.tipo_detectado.value: clf
            for clf in clasificaciones.values()
        }

        estado = self._motor.evaluar_checklist(tipo_tramite, docs_por_requisito)
        resultado.estado_checklist = estado

        if estado.debe_pedir_gestoria:
            cuerpo = self._motor.preparar_mensaje_gestoria(estado, matricula=matricula)
            msg = _preparar_aviso(
                tramite_id=tramite_id,
                destinatario=gestoria_email,
                tipo=TipoMensajeSaliente.AVISO_1,
                cuerpo=cuerpo,
                matricula=matricula,
            )
            self._repo.guardar_mensaje_saliente(msg)
            resultado.mensajes_preparados.append(msg)
            logger.info(
                "Trámite %s: aviso_1 preparado para %s (%d faltantes, %d evidencia).",
                tramite_id, gestoria_email,
                len(estado.requisitos_faltantes), len(estado.requisitos_evidencia),
            )

        if estado.debe_escalar_admin:
            s = get_settings()
            if s.email_administrativo:
                cuerpo_admin = (
                    f"Expediente {tramite_id} — documentos rechazados:\n"
                    + "\n".join(f"  • {r}" for r in estado.requisitos_rechazados)
                    + "\n\nRequiere revisión manual."
                )
                msg_admin = _preparar_aviso(
                    tramite_id=tramite_id,
                    destinatario=s.email_administrativo,
                    tipo=TipoMensajeSaliente.ESCALADO,
                    cuerpo=cuerpo_admin,
                    matricula=matricula,
                )
                self._repo.guardar_mensaje_saliente(msg_admin)
                resultado.mensajes_preparados.append(msg_admin)
                logger.warning(
                    "Trámite %s: escalado al administrativo (%d rechazados).",
                    tramite_id, len(estado.requisitos_rechazados),
                )

        ep.estado = EstadoEmail.PROCESADO if ep.estado != EstadoEmail.ERROR else ep.estado
        self._repo.guardar_email_procesado(ep)
        return resultado

    def ejecutar_timers(self, ahora: datetime | None = None) -> list[MensajeSaliente]:
        """Revisa los timers de escalado y prepara los mensajes que correspondan.

        Llamar periódicamente (cron o background task de FastAPI).
        Devuelve los mensajes nuevos preparados en esta ejecución.

        T+30 → aviso_2 si aviso_1 no fue respondido
        T+60 → escalado al admin si aviso_2 no fue respondido
        """
        ahora = ahora or datetime.utcnow()
        nuevos: list[MensajeSaliente] = []
        s = get_settings()

        for tramite_id, destinatario, _ in self._repo.mensajes_pendientes_de_aviso2(ahora):
            msg = MensajeSaliente(
                tramite_id=tramite_id,
                destinatario=destinatario,
                tipo=TipoMensajeSaliente.AVISO_2,
                asunto=f"Tyrion — recordatorio urgente de documentación",
                cuerpo=(
                    f"Este es un recordatorio urgente para el expediente {tramite_id}.\n"
                    "La documentación sigue pendiente. Por favor envíela a la brevedad."
                ),
                preparado_at=ahora,
            )
            self._repo.guardar_mensaje_saliente(msg)
            nuevos.append(msg)
            logger.info("Timer aviso_2 disparado para trámite %s.", tramite_id)

        for tramite_id, _, _ in self._repo.mensajes_pendientes_de_escalado(ahora):
            if not s.email_administrativo:
                continue
            msg = MensajeSaliente(
                tramite_id=tramite_id,
                destinatario=s.email_administrativo,
                tipo=TipoMensajeSaliente.ESCALADO,
                asunto=f"Tyrion — expediente escalado al administrativo",
                cuerpo=(
                    f"El expediente {tramite_id} lleva más de {s.escalado_admin_min} minutos "
                    "sin documentación completa. La gestoría no respondió los avisos.\n"
                    "Se requiere intervención manual."
                ),
                preparado_at=ahora,
            )
            self._repo.guardar_mensaje_saliente(msg)
            nuevos.append(msg)
            logger.warning("Timer escalado disparado para trámite %s.", tramite_id)

        return nuevos
