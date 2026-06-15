"""
Tests de la ingesta de email.

Sin red: la fuente IMAP se reemplaza por una fuente en memoria que devuelve
emails RFC822 construidos en el propio test. Verifica parsing, extracción de
adjuntos y deduplicación por Message-ID.
"""
import email as email_lib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from app.services.ingesta_email import (
    IngestaEmail,
    parsear_email,
)


# ---------- helpers ----------

def _construir_email_raw(
    message_id: str,
    remitente: str = "gestoria@example.com",
    asunto: str = "Documentos trámite",
    adjuntos: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Construye un email RFC822 mínimo con los adjuntos indicados."""
    msg = MIMEMultipart()
    msg["Message-ID"] = message_id
    msg["From"] = remitente
    msg["Subject"] = asunto
    msg["Date"] = "Mon, 15 Jun 2026 10:00:00 +0000"
    msg.attach(MIMEText("Adjunto la documentación.", "plain"))
    for nombre, contenido in (adjuntos or []):
        adjunto = MIMEApplication(contenido, Name=nombre)
        adjunto["Content-Disposition"] = f'attachment; filename="{nombre}"'
        msg.attach(adjunto)
    return msg.as_bytes()


class FuenteEnMemoria:
    """Fuente de correo en memoria para tests."""
    def __init__(self, crudos: list[bytes]):
        self._crudos = crudos

    def mensajes_crudos(self) -> list[bytes]:
        return self._crudos


# ---------- parsear_email: función pura ----------

def test_parsea_campos_basicos():
    raw = _construir_email_raw("<id-001@test>", remitente="g@gestor.es", asunto="Docs")
    em = parsear_email(raw)
    assert em.message_id == "<id-001@test>"
    assert em.remitente == "g@gestor.es"
    assert em.asunto == "Docs"


def test_extrae_adjunto_pdf():
    raw = _construir_email_raw(
        "<id-002@test>",
        adjuntos=[("permiso.pdf", b"%PDF-1.4 contenido")],
    )
    em = parsear_email(raw)
    assert len(em.adjuntos) == 1
    assert em.adjuntos[0].nombre == "permiso.pdf"
    assert em.adjuntos[0].contenido == b"%PDF-1.4 contenido"
    assert em.tiene_adjuntos_utiles


def test_extrae_adjunto_imagen():
    raw = _construir_email_raw(
        "<id-003@test>",
        adjuntos=[("dni.jpg", b"\xff\xd8\xff imagen")],
    )
    em = parsear_email(raw)
    assert len(em.adjuntos) == 1
    assert em.adjuntos[0].nombre == "dni.jpg"


def test_ignora_adjunto_no_soportado():
    """Los .docx y similares no los puede leer el clasificador → se descartan."""
    raw = _construir_email_raw(
        "<id-004@test>",
        adjuntos=[
            ("informe.docx", b"contenido word"),
            ("permiso.pdf", b"%PDF-1.4 ok"),
        ],
    )
    em = parsear_email(raw)
    assert len(em.adjuntos) == 1
    assert em.adjuntos[0].nombre == "permiso.pdf"


def test_email_sin_adjuntos():
    raw = _construir_email_raw("<id-005@test>")
    em = parsear_email(raw)
    assert em.adjuntos == []
    assert not em.tiene_adjuntos_utiles


def test_multiples_adjuntos():
    raw = _construir_email_raw(
        "<id-006@test>",
        adjuntos=[
            ("permiso.pdf", b"%PDF permiso"),
            ("modelo620.pdf", b"%PDF 620"),
            ("dni.png", b"\x89PNG dni"),
        ],
    )
    em = parsear_email(raw)
    assert len(em.adjuntos) == 3


# ---------- IngestaEmail: deduplicación ----------

def test_poll_retorna_emails_nuevos():
    raw = _construir_email_raw("<nuevo@test>", adjuntos=[("doc.pdf", b"%PDF")])
    ingesta = IngestaEmail(fuente=FuenteEnMemoria([raw]))
    vistos: set[str] = set()
    nuevos = ingesta.poll(vistos)
    assert len(nuevos) == 1
    assert nuevos[0].message_id == "<nuevo@test>"
    assert "<nuevo@test>" in vistos


def test_poll_deduplica_por_message_id():
    """El mismo email no se procesa dos veces aunque llegue dos veces del IMAP."""
    raw = _construir_email_raw("<dup@test>", adjuntos=[("doc.pdf", b"%PDF")])
    fuente = FuenteEnMemoria([raw, raw])
    ingesta = IngestaEmail(fuente=fuente)
    vistos: set[str] = set()
    nuevos = ingesta.poll(vistos)
    assert len(nuevos) == 1


def test_poll_omite_ya_vistos():
    raw = _construir_email_raw("<ya-visto@test>", adjuntos=[("doc.pdf", b"%PDF")])
    ingesta = IngestaEmail(fuente=FuenteEnMemoria([raw]))
    vistos = {"<ya-visto@test>"}
    nuevos = ingesta.poll(vistos)
    assert nuevos == []


def test_poll_descarta_sin_message_id():
    """Email sin Message-ID: se descarta (no hay clave de dedup)."""
    msg = MIMEText("sin id")
    msg["From"] = "x@x.com"
    raw = msg.as_bytes()
    ingesta = IngestaEmail(fuente=FuenteEnMemoria([raw]))
    vistos: set[str] = set()
    nuevos = ingesta.poll(vistos)
    assert nuevos == []


def test_poll_varios_emails_distintos():
    raws = [
        _construir_email_raw(f"<mail-{i}@test>", adjuntos=[("doc.pdf", b"%PDF")])
        for i in range(5)
    ]
    ingesta = IngestaEmail(fuente=FuenteEnMemoria(raws))
    vistos: set[str] = set()
    nuevos = ingesta.poll(vistos)
    assert len(nuevos) == 5
    assert len(vistos) == 5
