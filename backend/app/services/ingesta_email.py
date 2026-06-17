"""
Ingesta de email de Tyrion — entrada principal de documentación.

Las gestorías envían la documentación de los trámites por email (canal EMAIL del
schema). Este módulo:
  - Se conecta a un buzón IMAP genérico (Gmail con app password para pruebas,
    buzón corporativo en producción; todo por variables de entorno).
  - Hace polling de los mensajes no procesados, deduplicando por Message-ID.
  - Extrae los adjuntos PDF e imagen, que son los que el clasificador sabe leer.

Diseño testeable: la conexión IMAP real (`FuenteIMAP`) se separa del parsing.
El parsing (`parsear_email`) es puro y los tests inyectan una fuente en memoria,
sin tocar la red.
"""
from __future__ import annotations

import email
import imaplib
import logging
from dataclasses import dataclass, field
from email.message import Message
from email.utils import parseaddr
from typing import Protocol

from app.core.config import get_settings
from app.services.clasificador import MEDIA_TYPES

logger = logging.getLogger(__name__)

# Extensiones que el clasificador puede leer (reutiliza el contrato del clasificador).
EXTENSIONES_SOPORTADAS = set(MEDIA_TYPES.keys())


@dataclass
class AdjuntoEmail:
    """Un adjunto extraído de un email."""
    nombre: str
    content_type: str
    contenido: bytes


@dataclass
class EmailEntrante:
    """Un email ya parseado, listo para el pipeline."""
    message_id: str
    remitente: str
    asunto: str
    fecha: str
    adjuntos: list[AdjuntoEmail] = field(default_factory=list)

    @property
    def tiene_adjuntos_utiles(self) -> bool:
        return bool(self.adjuntos)


def _nombre_adjunto(part: Message) -> str | None:
    """Nombre del adjunto si la parte es un documento adjunto soportado."""
    nombre = part.get_filename()
    if not nombre:
        return None
    ext = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""
    if ext not in EXTENSIONES_SOPORTADAS:
        return None
    return nombre


def _extraer_adjuntos(msg: Message) -> list[AdjuntoEmail]:
    """Recorre el árbol MIME y extrae los adjuntos PDF/imagen soportados."""
    adjuntos: list[AdjuntoEmail] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        nombre = _nombre_adjunto(part)
        if nombre is None:
            continue
        contenido = part.get_payload(decode=True)
        if not contenido:
            continue
        adjuntos.append(
            AdjuntoEmail(
                nombre=nombre,
                content_type=part.get_content_type(),
                contenido=contenido,
            )
        )
    return adjuntos


def parsear_email(raw: bytes) -> EmailEntrante:
    """Parsea los bytes crudos de un email (RFC822) a un EmailEntrante.

    Función pura: no toca la red ni el disco. Es el núcleo testeable de la ingesta.
    """
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip()
    remitente = parseaddr(msg.get("From", ""))[1].lower()
    asunto = msg.get("Subject", "") or ""
    fecha = msg.get("Date", "") or ""
    return EmailEntrante(
        message_id=message_id,
        remitente=remitente,
        asunto=asunto,
        fecha=fecha,
        adjuntos=_extraer_adjuntos(msg),
    )


class FuenteCorreo(Protocol):
    """Origen de mensajes crudos. Abstrae IMAP para poder testear sin red."""

    def mensajes_crudos(self) -> list[bytes]:
        """Devuelve los emails crudos (RFC822) pendientes de procesar."""
        ...


class FuenteIMAP:
    """Fuente de correo real sobre IMAP (Gmail u otro buzón corporativo).

    Trae los mensajes NO leídos del buzón. La deduplicación fina por Message-ID
    la hace `IngestaEmail` aguas arriba, de modo que un mensaje ya procesado nunca
    se reinyecta aunque el flag de leído se pierda.
    """

    def __init__(self, settings=None):
        self._s = settings or get_settings()

    def mensajes_crudos(self) -> list[bytes]:
        if not self._s.imap_host:
            logger.warning("IMAP no configurado (imap_host vacío); no se hace polling.")
            return []

        crudos: list[bytes] = []
        conn = imaplib.IMAP4_SSL(self._s.imap_host, self._s.imap_port, timeout=30)
        try:
            conn.login(self._s.imap_user, self._s.imap_password)
            conn.select(self._s.imap_mailbox)
            estado, datos = conn.search(None, "UNSEEN")
            if estado != "OK":
                logger.error("IMAP SEARCH falló: %s", estado)
                return []
            for num in datos[0].split():
                estado, msg_data = conn.fetch(num, "(RFC822)")
                if estado != "OK" or not msg_data:
                    continue
                for parte in msg_data:
                    if isinstance(parte, tuple) and parte[1]:
                        crudos.append(parte[1])
        finally:
            try:
                conn.logout()
            except Exception:  # pragma: no cover - cierre best-effort
                pass
        return crudos


class IngestaEmail:
    """Hace polling de una fuente de correo y entrega emails deduplicados.

    `vistos` es el conjunto de Message-IDs ya procesados (lo provee la capa de
    persistencia: tabla `emails_procesados`). Un email sin Message-ID o ya visto
    se descarta.
    """

    def __init__(self, fuente: FuenteCorreo | None = None):
        self._fuente = fuente or FuenteIMAP()

    def poll(self, vistos: set[str]) -> list[EmailEntrante]:
        nuevos: list[EmailEntrante] = []
        for raw in self._fuente.mensajes_crudos():
            em = parsear_email(raw)
            if not em.message_id:
                logger.warning("Email sin Message-ID descartado (remitente=%s).", em.remitente)
                continue
            if em.message_id in vistos:
                continue
            vistos.add(em.message_id)
            nuevos.append(em)
        return nuevos
