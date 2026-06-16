"""
Deducción del tipo de trámite a partir de los documentos clasificados.

Principio rector (sesión 12): el administrativo NO declara el tipo de trámite.
Tyrion lo infiere viendo qué documentos llegaron. El DOCUMENTO PRINCIPAL
define el tipo:

  - Solicitud de Matriculación  → MATRICULACION
  - Solicitud de Baja           → BAJA
  - CTI / contrato compraventa  → TRANSFERENCIA
  - Modelo 650 / herederos      → TRANSFERENCIA (subtipo herencia)

Si ningún documento principal aparece, se usa una heurística de respaldo sobre
los documentos secundarios; si aun así no hay señal, se devuelve None y el
trámite queda para revisión manual del administrativo.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.catalogo_documental import (
    TipoDocumento,
    TipoTramite,
    SubtipoTramite,
)


@dataclass
class DeduccionTipo:
    """Resultado de deducir el tipo de trámite."""
    tipo: TipoTramite | None
    subtipo: SubtipoTramite
    motivo: str
    documento_principal: str | None   # tipo del doc que decidió

    @property
    def deducido(self) -> bool:
        return self.tipo is not None


# Documentos PRINCIPALES: su sola presencia define el tipo de trámite.
# El orden importa: el primero que aparezca gana (mayor especificidad arriba).
_PRINCIPALES: list[tuple[TipoDocumento, TipoTramite]] = [
    (TipoDocumento.SOLICITUD_MATRICULACION, TipoTramite.MATRICULACION),
    (TipoDocumento.SOLICITUD_BAJA,          TipoTramite.BAJA),
    (TipoDocumento.CTI,                     TipoTramite.TRANSFERENCIA),
    (TipoDocumento.CONTRATO_COMPRAVENTA,    TipoTramite.TRANSFERENCIA),
]

# Documentos que sugieren herencia dentro de una transferencia.
_SENALES_HERENCIA = {
    TipoDocumento.MODELO_650,
    TipoDocumento.DECLARACION_HEREDEROS,
    TipoDocumento.ANEXO_650,
    TipoDocumento.CERTIFICADO_DEFUNCION,
}

# Respaldo: documentos secundarios que orientan si no hay principal.
_RESPALDO: list[tuple[TipoDocumento, TipoTramite]] = [
    (TipoDocumento.IMPUESTO_MATRICULACION, TipoTramite.MATRICULACION),
    (TipoDocumento.IVTM,                   TipoTramite.MATRICULACION),
    (TipoDocumento.MODELO_620,             TipoTramite.TRANSFERENCIA),
    (TipoDocumento.MODELO_650,             TipoTramite.TRANSFERENCIA),
]


def deducir_tipo_tramite(tipos_detectados: list[TipoDocumento]) -> DeduccionTipo:
    """Deduce el tipo de trámite a partir de los tipos de documento detectados.

    Args:
        tipos_detectados: lista de TipoDocumento de los documentos cargados.

    Returns:
        DeduccionTipo con tipo, subtipo, motivo y el documento que lo decidió.
    """
    presentes = set(tipos_detectados)

    # ¿Hay señales de herencia? Solo aplica a transferencia.
    hay_herencia = bool(presentes & _SENALES_HERENCIA)

    # 1. Documento principal define el tipo
    for doc_principal, tipo in _PRINCIPALES:
        if doc_principal in presentes:
            subtipo = SubtipoTramite.NINGUNO
            motivo = f"Documento principal '{doc_principal.value}' → {tipo.value}"
            if tipo == TipoTramite.TRANSFERENCIA and hay_herencia:
                subtipo = SubtipoTramite.HERENCIA
                motivo += " (subtipo herencia: detectado modelo 650 / declaración herederos)"
            return DeduccionTipo(
                tipo=tipo,
                subtipo=subtipo,
                motivo=motivo,
                documento_principal=doc_principal.value,
            )

    # 2. Respaldo: documentos secundarios
    for doc_respaldo, tipo in _RESPALDO:
        if doc_respaldo in presentes:
            subtipo = SubtipoTramite.NINGUNO
            motivo = f"Sin documento principal; inferido por '{doc_respaldo.value}' → {tipo.value}"
            if tipo == TipoTramite.TRANSFERENCIA and hay_herencia:
                subtipo = SubtipoTramite.HERENCIA
            return DeduccionTipo(
                tipo=tipo,
                subtipo=subtipo,
                motivo=motivo,
                documento_principal=None,
            )

    # 3. Sin señal suficiente → revisión manual
    return DeduccionTipo(
        tipo=None,
        subtipo=SubtipoTramite.NINGUNO,
        motivo="No se pudo deducir el tipo de trámite a partir de los documentos.",
        documento_principal=None,
    )
