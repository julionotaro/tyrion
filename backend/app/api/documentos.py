"""
API de documentos — endpoints para el Split-view documental.

Permite al frontend mostrar:
  - Lista de documentos de un trámite con su validez
  - Datos extraídos + resultado del cotejo por documento
  - (Futuro) el archivo PDF/imagen original

En modo USE_DATOS_PRUEBA los documentos con id vienen del catálogo
DOCUMENTOS_PRUEBA. Los que tienen id=None son simulados sin extracción detallada.

TODO sesión 6:
  - GET /api/documentos/{doc_id}/archivo → servir el PDF real desde uploads_dir
  - Integración con PostgreSQL: buscar documentos en tabla `documentos`
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.datos_prueba import DOCUMENTOS_PRUEBA, TRAMITES_PRUEBA
from app.api.deps import get_usar_datos_prueba

router = APIRouter(prefix="/api", tags=["documentos"])


# ---------- schemas ----------

class CampoExtraido(BaseModel):
    campo: str
    valor: str
    estado: str   # "valido" | "evidencia" | "rechazado" | "ilegible"


class DocumentoResumen(BaseModel):
    id: str | None
    nombre: str
    tipo_detectado: str
    validez: str
    confianza: str
    tiene_extraccion: bool


class DocumentoExtraccion(BaseModel):
    id: str
    tramite_id: str
    nombre: str
    tipo_detectado: str
    validez: str
    confianza: str
    confianza_score: float
    tiene_archivo: bool
    campos_extraidos: list[CampoExtraido]
    justificacion: str


# ---------- helpers ----------

def _tramite_o_404(tramite_id: str) -> dict[str, Any]:
    t = next((t for t in TRAMITES_PRUEBA if t["id"] == tramite_id), None)
    if not t:
        raise HTTPException(404, f"Trámite '{tramite_id}' no encontrado.")
    return t


# ---------- endpoints ----------

@router.get("/tramites/{tramite_id}/documentos", response_model=list[DocumentoResumen])
def listar_documentos(
    tramite_id: str,
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> list[DocumentoResumen]:
    """Lista de documentos de un trámite con su validez.

    Los documentos con id tienen extracción detallada disponible.
    Los que tienen id=None son registros básicos (sin extracción en datos de prueba).
    """
    tramite = _tramite_o_404(tramite_id)
    return [
        DocumentoResumen(
            id=doc.get("id"),
            nombre=doc["nombre"],
            tipo_detectado=doc["tipo_detectado"],
            validez=doc["validez"],
            confianza=doc["confianza"],
            tiene_extraccion=doc.get("id") is not None and doc["id"] in DOCUMENTOS_PRUEBA,
        )
        for doc in tramite.get("documentos", [])
    ]


@router.get("/documentos/{doc_id}/extraccion", response_model=DocumentoExtraccion)
def extraccion_documento(
    doc_id: str,
    usar_prueba: bool = Depends(get_usar_datos_prueba),
) -> DocumentoExtraccion:
    """Datos extraídos y resultado de cotejo de un documento específico.

    Alimenta el panel derecho del Split-view: campos detectados con su
    indicador visual (✓ verde / ⚠ naranja / ✗ rojo).
    """
    doc = DOCUMENTOS_PRUEBA.get(doc_id)
    if not doc:
        raise HTTPException(404, f"Documento '{doc_id}' no encontrado o sin extracción.")
    return DocumentoExtraccion(
        id=doc["id"],
        tramite_id=doc["tramite_id"],
        nombre=doc["nombre"],
        tipo_detectado=doc["tipo_detectado"],
        validez=doc["validez"],
        confianza=doc["confianza"],
        confianza_score=doc.get("confianza_score", 0.0),
        tiene_archivo=doc.get("tiene_archivo", False),
        campos_extraidos=[CampoExtraido(**c) for c in doc.get("campos_extraidos", [])],
        justificacion=doc.get("justificacion", ""),
    )


@router.get("/documentos/{doc_id}/archivo")
def archivo_documento(doc_id: str) -> dict[str, str]:
    """Sirve el archivo original del documento (PDF/imagen).

    TODO sesión 6: servir desde uploads_dir con FileResponse.
    Por ahora devuelve un placeholder indicando que el archivo no está disponible
    en modo de prueba.
    """
    doc = DOCUMENTOS_PRUEBA.get(doc_id)
    if not doc:
        raise HTTPException(404, f"Documento '{doc_id}' no encontrado.")
    if not doc.get("tiene_archivo", False):
        raise HTTPException(
            503,
            "Archivo no disponible en modo de prueba. "
            "En producción se servirá desde uploads_dir.",
        )
    # TODO: return FileResponse(ruta, media_type="application/pdf")
    raise HTTPException(501, "Servicio de archivos no implementado todavía.")
