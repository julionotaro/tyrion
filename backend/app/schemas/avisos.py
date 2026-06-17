"""Schema fijo de avisos pendientes de un trámite.

Las claves que el frontend (index.html) lee son: tipo, enviado_at, requisito.
Este schema garantiza que backend y frontend hablan el mismo lenguaje.
"""
from pydantic import BaseModel


class AvisoPendiente(BaseModel):
    """Aviso pendiente de envío a la gestoría.

    Campos que el frontend de Pantalla Control espera (index.html línea 784-786):
      - tipo       : "AVISO_1" | "AVISO_2" | "ESCALADO"
      - enviado_at : ISO timestamp (o preparado_at si aún no se envió)
      - requisito  : documento que falta o motivo del aviso
    """
    tipo: str         # AVISO_1 | AVISO_2 | ESCALADO
    enviado_at: str   # ISO timestamp — "preparado" aunque no enviado todavía
    requisito: str    # clave canónica del documento faltante o descripción breve
