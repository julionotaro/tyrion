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

    @property
    def requiere_validacion_humana(self) -> bool:
        """Confianza baja -> marca para revisión del administrativo."""
        return self.confianza_nivel == "BAJA"
