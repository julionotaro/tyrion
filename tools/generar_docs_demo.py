#!/usr/bin/env python3
"""
Genera PDFs de muestra para la demo de carga manual.

4 trámites de ejemplo:
  1. Transferencia completa (CTI + 620 + DNI + contrato) → listo_dgt
  2. Transferencia con CTI faltante del modelo_620 → pide a gestoría
  3. Transferencia real: CTI + 620 + DNI (falta contrato)
  4. Matriculación tipo A completa

Uso:
  python tools/generar_docs_demo.py
  → Genera /tmp/tyrion_demo/ con los PDFs listos para cargar en carga.html
"""
from pathlib import Path

DEMO_DIR = Path("/tmp/tyrion_demo")

DOCS = {
    # Trámite 1: transferencia completa
    "tramite1_cti.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 280>>stream
BT /F1 16 Tf 50 780 Td (CERTIFICADO DE TRANSFERENCIA INDIVIDUAL) Tj
/F1 11 Tf 0 -30 Td (CTI - DGT) Tj
0 -20 Td (Matricula: 1234 ABC) Tj
0 -20 Td (Bastidor: VS6RFD000X1234567) Tj
0 -20 Td (Titular transmitente: Juan Garcia Lopez) Tj
0 -20 Td (NIF transmitente: 12345678A) Tj
0 -20 Td (Titular adquirente: Maria Perez Ruiz) Tj
0 -20 Td (NIF adquirente: 87654321B) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 650
%%EOF""",

    "tramite1_620.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 220>>stream
BT /F1 16 Tf 50 780 Td (MODELO 620 - TRANSMISIONES PATRIMONIALES) Tj
/F1 11 Tf 0 -30 Td (Agencia Tributaria de Galicia) Tj
0 -20 Td (Matricula: 1234 ABC) Tj
0 -20 Td (Importe: 8.500,00 EUR) Tj
0 -20 Td (Fecha liquidacion: 10/06/2026) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 590
%%EOF""",

    "tramite1_dni.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 180>>stream
BT /F1 16 Tf 50 780 Td (DOCUMENTO NACIONAL DE IDENTIDAD) Tj
/F1 11 Tf 0 -30 Td (DNI) Tj
0 -20 Td (Nombre: MARIA PEREZ RUIZ) Tj
0 -20 Td (NIF: 87654321B) Tj
0 -20 Td (Fecha nacimiento: 15/03/1985) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 550
%%EOF""",

    "tramite1_contrato.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 200>>stream
BT /F1 16 Tf 50 780 Td (CONTRATO DE COMPRAVENTA) Tj
/F1 11 Tf 0 -30 Td (Vehiculo: SEAT Ibiza - 1234 ABC) Tj
0 -20 Td (Vendedor: Juan Garcia Lopez - 12345678A) Tj
0 -20 Td (Comprador: Maria Perez Ruiz - 87654321B) Tj
0 -20 Td (Precio acordado: 8.500 EUR) Tj
0 -20 Td (Fecha: 08/06/2026) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 560
%%EOF""",

    # Trámite 2: transferencia incompleta (falta contrato y modelo 620)
    "tramite2_cti.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 260>>stream
BT /F1 16 Tf 50 780 Td (CERTIFICADO DE TRANSFERENCIA INDIVIDUAL) Tj
/F1 11 Tf 0 -30 Td (CTI - DGT) Tj
0 -20 Td (Matricula: 5678 DEF) Tj
0 -20 Td (Bastidor: WVWZZZ3BZXE123456) Tj
0 -20 Td (Titular transmitente: Carlos Fernandez) Tj
0 -20 Td (Titular adquirente: Laura Sanchez) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 620
%%EOF""",

    "tramite2_dni.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 170>>stream
BT /F1 16 Tf 50 780 Td (DOCUMENTO NACIONAL DE IDENTIDAD) Tj
/F1 11 Tf 0 -30 Td (Nombre: LAURA SANCHEZ GOMEZ) Tj
0 -20 Td (NIF: 11223344C) Tj
0 -20 Td (Fecha nacimiento: 22/07/1990) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 540
%%EOF""",

    # Trámite 4: matriculación tipo A
    "tramite4_solicitud.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 200>>stream
BT /F1 16 Tf 50 780 Td (SOLICITUD DE MATRICULACION) Tj
/F1 11 Tf 0 -30 Td (Impreso oficial DGT) Tj
0 -20 Td (Titular: Pedro Alvarez Martinez) Tj
0 -20 Td (NIF: 44332211D) Tj
0 -20 Td (Marca/Modelo: Toyota Corolla) Tj
0 -20 Td (Fecha solicitud: 16/06/2026) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 560
%%EOF""",

    "tramite4_ficha_tecnica.pdf": b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 200>>stream
BT /F1 16 Tf 50 780 Td (FICHA TECNICA DEL VEHICULO) Tj
/F1 11 Tf 0 -30 Td (Marca: Toyota / Modelo: Corolla) Tj
0 -20 Td (Bastidor: JTDKN3DU0A3123456) Tj
0 -20 Td (Potencia: 90 kW) Tj
0 -20 Td (Combustible: Hibrido) Tj
0 -20 Td (Homologacion: e11*2007/46*0145*01) Tj
ET
endstream
endobj
xref 0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000316 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref 560
%%EOF""",
}


def main():
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in DOCS.items():
        (DEMO_DIR / nombre).write_bytes(contenido)
    print(f"✓ {len(DOCS)} documentos de demo generados en {DEMO_DIR}")
    print()
    print("Trámites para la demo:")
    print("  Trámite 1 (transferencia COMPLETA): tramite1_cti.pdf + tramite1_620.pdf + tramite1_dni.pdf + tramite1_contrato.pdf")
    print("  Trámite 2 (transferencia INCOMPLETA): tramite2_cti.pdf + tramite2_dni.pdf  → falta 620 y contrato")
    print("  Trámite 4 (matriculación): tramite4_solicitud.pdf + tramite4_ficha_tecnica.pdf")
    print()
    print(f"Cargar en: http://localhost:8000/static/carga.html")


if __name__ == "__main__":
    main()
