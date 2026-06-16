import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.storage import guardar_archivo

DOCS = [
    ("doc-001", "cti.pdf", "Certificado de Transferencia Individual"),
    ("doc-002", "modelo_620.pdf", "Modelo 620 - Transmisiones"),
    ("doc-003", "dni.pdf", "DNI - Documento Nacional de Identidad"),
    ("doc-004", "hoja_de_caja.pdf", "Hoja de Caja"),
    ("doc-005", "cti_extra.pdf", "CTI - Evidencia Compatible"),
    ("doc-006", "permiso_circulacion.pdf", "Permiso de Circulacion"),
    ("doc-007", "solicitud_baja.pdf", "Solicitud de Baja"),
    ("doc-008", "ficha_tecnica.pdf", "Ficha Tecnica del Vehiculo"),
]


def _pdf_minimo(titulo: str) -> bytes:
    content = f"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>
stream
BT /F1 12 Tf 100 700 Td ({titulo}) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
trailer<</Size 5/Root 1 0 R>>
startxref
360
%%EOF"""
    return content.encode()


def main():
    for doc_id, nombre, titulo in DOCS:
        ruta = guardar_archivo(doc_id, _pdf_minimo(titulo), nombre, "application/pdf")
        print(f"  {doc_id} -> {ruta}")
    print("Documentos de prueba cargados.")


if __name__ == "__main__":
    main()
