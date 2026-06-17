"""Schemas de entrada/salida del clasificador documental."""
from pydantic import BaseModel, Field
from app.services.catalogo_documental import TipoDocumento


class ResultadoClasificacion(BaseModel):
    """Resultado de clasificar un documento. Mapea a las capas 3 del modelo:
    el tipo DETECTADO con su nivel de confianza."""

    tipo_detectado: TipoDocumento
    confianza_score: float = Field(ge=0.0, le=1.0)
    confianza_nivel: str  # ALTA / MEDIA / BAJA
    # datos extraídos relevantes para el cotejo (matrícula, titular, etc.)
    datos_extraidos: dict = Field(default_factory=dict)
    # razonamiento breve de por qué se clasificó así (para auditoría)
    justificacion: str = ""
    # si el tipo declarado por el remitente NO coincide con lo detectado
    discrepancia_con_declarado: bool = False
    # True si la confianza es BAJA o la extracción está incompleta
    requiere_validacion_humana: bool = False
    # campos que deberían haberse extraído y no aparecen
    campos_faltantes: list[str] = Field(default_factory=list)
