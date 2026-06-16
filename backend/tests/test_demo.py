"""Smoke test: cargar_docs_prueba script runs without exceptions."""
import importlib.util, sys, os
from pathlib import Path
from unittest.mock import patch


def test_cargar_docs_prueba_no_lanza(tmp_path):
    tools_dir = Path(__file__).parent.parent.parent / "tools"
    spec = importlib.util.spec_from_file_location("cargar_docs_prueba", tools_dir / "cargar_docs_prueba.py")
    module = importlib.util.module_from_spec(spec)

    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    with patch("app.services.storage._uploads_dir", return_value=tmp_path):
        spec.loader.exec_module(module)

    assert len(module.DOCS) == 8
    # Verify _pdf_minimo produces bytes
    pdf_bytes = module._pdf_minimo("Test")
    assert pdf_bytes.startswith(b"%PDF")
