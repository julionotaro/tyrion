"""
Modelos de persistencia para ingesta y mensajes salientes.

Deliberadamente simples: sin ORM pesado, solo dataclasses que mapean
a las tablas del schema. La capa de BD (asyncpg) los usa directamente.

Tablas nuevas (migración 002):
  emails_procesados   — deduplicación por Message-ID
  mensajes_salientes  — avisos a gestoría y escalados al admin (estado del ciclo)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TipoMensajeSaliente(str, Enum):
    AVISO_1 = "aviso_1"       # T+0  — primer aviso automático a gestoría
    AVISO_2 = "aviso_2"       # T+30 — segundo aviso automático
    ESCALADO = "escalado"     # T+60 — escalado al administrativo (último recurso)


class EstadoEmail(str, Enum):
    RECIBIDO = "RECIBIDO"
    PROCESADO = "PROCESADO"
    ERROR = "ERROR"


@dataclass
class EmailProcesado:
    """Registro de un email ya procesado (tabla emails_procesados).

    Garantiza idempotencia: si el mismo Message-ID llega dos veces
    (reenvío, fallo de marcado IMAP…) no se procesa de nuevo.
    """
    message_id: str
    remitente: str
    asunto: str
    fecha_recibido: datetime
    num_adjuntos: int = 0
    estado: EstadoEmail = EstadoEmail.RECIBIDO
    error_detalle: str = ""


@dataclass
class MensajeSaliente:
    """Aviso o escalado preparado por Tyrion (tabla mensajes_salientes).

    Principio del schema: PREPARADO ≠ ENVIADO. El estado empieza en PREPARADO
    y solo pasa a ENVIADO cuando hay integración de envío real confirmada.

    Orden de escalado (hardcodeado en pipeline.py, configurable en settings):
      aviso_1  → T+0   gestoría
      aviso_2  → T+30  gestoría
      escalado → T+60  administrativo (último recurso)
    """
    tramite_id: str
    destinatario: str
    tipo: TipoMensajeSaliente
    asunto: str
    cuerpo: str
    preparado_at: datetime = field(default_factory=datetime.utcnow)
    enviado_at: datetime | None = None
    respondido_at: datetime | None = None
    # NULL = PREPARADO; se actualiza al enviar
    enviado: bool = False
