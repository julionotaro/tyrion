"""Tests for storage.py — local file storage."""
import pytest
from unittest.mock import patch
from pathlib import Path
import tempfile


def test_guardar_y_obtener_archivo(tmp_path):
    with patch("app.services.storage._uploads_dir", return_value=tmp_path):
        from app.services.storage import guardar_archivo, obtener_archivo
        guardar_archivo("doc-test", b"%PDF test content", "test.pdf", "application/pdf")
        contenido, mime = obtener_archivo("doc-test")
        assert contenido == b"%PDF test content"
        assert mime == "application/pdf"


def test_obtener_archivo_no_existente(tmp_path):
    with patch("app.services.storage._uploads_dir", return_value=tmp_path):
        from app.services.storage import obtener_archivo
        with pytest.raises(FileNotFoundError):
            obtener_archivo("doc-inexistente")


def test_guardar_crea_directorio(tmp_path):
    with patch("app.services.storage._uploads_dir", return_value=tmp_path):
        from app.services.storage import guardar_archivo
        guardar_archivo("doc-nuevo", b"content", "archivo.pdf", "application/pdf")
        assert (tmp_path / "doc-nuevo" / "archivo.pdf").exists()


def test_mime_pdf():
    # PDF files detected by extension
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        with patch("app.services.storage._uploads_dir", return_value=Path(d)):
            from app.services.storage import guardar_archivo, obtener_archivo
            guardar_archivo("doc-pdf", b"%PDF-1.4", "documento.pdf", "application/pdf")
            _, mime = obtener_archivo("doc-pdf")
            assert mime == "application/pdf"
