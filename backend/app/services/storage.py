"""Simple local file storage for uploaded documents."""
import os
from pathlib import Path
from app.core.config import get_settings


def _uploads_dir() -> Path:
    s = get_settings()
    d = Path(getattr(s, "uploads_dir", "/tmp/tyrion_uploads"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def guardar_archivo(doc_id: str, contenido: bytes, nombre: str, mime_type: str) -> str:
    """Saves file to uploads/{doc_id}/{nombre}. Returns relative path."""
    doc_dir = _uploads_dir() / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    ruta = doc_dir / nombre
    ruta.write_bytes(contenido)
    return str(ruta)


def obtener_archivo(doc_id: str) -> tuple[bytes, str]:
    """Returns (bytes, mime_type). Raises FileNotFoundError if missing."""
    doc_dir = _uploads_dir() / doc_id
    if not doc_dir.exists():
        raise FileNotFoundError(f"No file found for doc_id={doc_id}")
    for f in doc_dir.iterdir():
        mime = "application/pdf" if f.suffix.lower() == ".pdf" else "image/jpeg"
        return f.read_bytes(), mime
    raise FileNotFoundError(f"No file found for doc_id={doc_id}")
