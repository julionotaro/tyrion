"""
Validaciones cruzadas multi-documento de Tyrion.

Implementa los cruces de la matriz §9 (docs/matriz-documental-tramites.md):
  - cruce_transferencia(): CET del CTI == CET del 620; bastidores consistentes
  - cruce_herencia():      causante(650) == fallecido(defunción) == titular CTI;
                           vehículo presente en Anexo 650
  - cruce_matriculacion(): bastidor consistente en solicitud + ficha + IVTM +
                           impuesto matriculación

Clave de cruce primaria = BASTIDOR (VIN, 17 caracteres).
La matrícula puede cambiar (nueva matriculación, cambio de domicilio, etc.);
el bastidor es inmutable a lo largo del ciclo de vida del vehículo.

TODO sesión siguiente:
  - Ingesta de planilla (Relación Transmisiones/Matrículas)
  - Cruce email ↔ planilla (trámites del día vs. correos recibidos)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SeveridadCruce(str, Enum):
    OK = "ok"
    EVIDENCIA = "evidencia"    # discrepancia recoverable: pedir aclaración a gestoría
    RECHAZADO = "rechazado"    # discrepancia grave: posible fraude o error crítico


@dataclass
class DiscrepanciaCruce:
    """Una discrepancia detectada entre dos campos de documentos distintos."""
    campo: str
    doc_a: str       # nombre/tipo del primer documento
    valor_a: str
    doc_b: str
    valor_b: str
    severidad: SeveridadCruce
    descripcion: str


@dataclass
class ResultadoCruce:
    """Resultado de un cruce multi-documento."""
    tipo_cruce: str
    discrepancias: list[DiscrepanciaCruce] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.discrepancias

    @property
    def severidad_maxima(self) -> SeveridadCruce:
        if not self.discrepancias:
            return SeveridadCruce.OK
        if any(d.severidad == SeveridadCruce.RECHAZADO for d in self.discrepancias):
            return SeveridadCruce.RECHAZADO
        return SeveridadCruce.EVIDENCIA

    @property
    def requiere_revision_manual(self) -> bool:
        return self.severidad_maxima == SeveridadCruce.RECHAZADO


def _normalizar_bastidor(v: str) -> str:
    return v.strip().upper().replace(" ", "").replace("-", "")


def _bastidores_divergen(a: str, b: str) -> bool:
    return bool(a and b and _normalizar_bastidor(a) != _normalizar_bastidor(b))


# ── Cruces ────────────────────────────────────────────────────────────────────

def cruce_transferencia(
    bastidor_permiso: str = "",
    bastidor_cti: str = "",
    bastidor_620: str = "",
    cet_cti: float | None = None,
    cet_620: float | None = None,
    nif_titular_permiso: str = "",
    nif_transmitente_dni: str = "",
    tolerancia_cet: float = 0.05,
) -> ResultadoCruce:
    """Cruces de una TRANSFERENCIA (matriz §9.2).

    Args:
        bastidor_permiso: bastidor extraído del permiso de circulación.
        bastidor_cti:     bastidor extraído del CTI.
        bastidor_620:     bastidor extraído del modelo 620.
        cet_cti:          CET (valor de mercado) del CTI.
        cet_620:          CET (base imponible) del modelo 620.
        nif_titular_permiso: NIF del titular en el permiso.
        nif_transmitente_dni: NIF del transmitente en el DNI.
        tolerancia_cet:   diferencia relativa máxima admitida entre CET del CTI y el 620.
    """
    resultado = ResultadoCruce(tipo_cruce="transferencia")

    # Cruce bastidor permiso ↔ CTI (fraude potencial si divergen)
    if _bastidores_divergen(bastidor_permiso, bastidor_cti):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="bastidor",
            doc_a="permiso_circulacion",
            valor_a=bastidor_permiso,
            doc_b="cti",
            valor_b=bastidor_cti,
            severidad=SeveridadCruce.RECHAZADO,
            descripcion=(
                f"Bastidor del permiso ({bastidor_permiso}) y del CTI ({bastidor_cti}) "
                "no coinciden. Posible sustitución de documento."
            ),
        ))

    # Cruce bastidor permiso ↔ 620
    if _bastidores_divergen(bastidor_permiso, bastidor_620):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="bastidor",
            doc_a="permiso_circulacion",
            valor_a=bastidor_permiso,
            doc_b="modelo_620",
            valor_b=bastidor_620,
            severidad=SeveridadCruce.RECHAZADO,
            descripcion=(
                f"Bastidor del permiso ({bastidor_permiso}) y del 620 ({bastidor_620}) "
                "no coinciden."
            ),
        ))

    # Cruce CET: CTI (valor tasado) vs 620 (base imponible)
    if cet_cti is not None and cet_620 is not None and cet_cti > 0:
        diferencia_rel = abs(cet_cti - cet_620) / cet_cti
        if diferencia_rel > tolerancia_cet:
            resultado.discrepancias.append(DiscrepanciaCruce(
                campo="cet",
                doc_a="cti",
                valor_a=str(cet_cti),
                doc_b="modelo_620",
                valor_b=str(cet_620),
                severidad=SeveridadCruce.EVIDENCIA,
                descripcion=(
                    f"CET del CTI ({cet_cti:.2f} €) y base imponible del 620 ({cet_620:.2f} €) "
                    f"difieren más del {tolerancia_cet*100:.0f}%. Pedir justificación a gestoría."
                ),
            ))

    # Cruce NIF transmitente: DNI vs titular del permiso
    if nif_titular_permiso and nif_transmitente_dni:
        if nif_titular_permiso.strip().upper() != nif_transmitente_dni.strip().upper():
            resultado.discrepancias.append(DiscrepanciaCruce(
                campo="nif_transmitente",
                doc_a="permiso_circulacion",
                valor_a=nif_titular_permiso,
                doc_b="dni",
                valor_b=nif_transmitente_dni,
                severidad=SeveridadCruce.EVIDENCIA,
                descripcion=(
                    f"NIF del titular en el permiso ({nif_titular_permiso}) "
                    f"difiere del NIF del DNI del transmitente ({nif_transmitente_dni}). "
                    "¿Titular ≠ vendedor? Pedir aclaración."
                ),
            ))

    return resultado


def cruce_herencia(
    nombre_causante_defuncion: str = "",
    nombre_causante_650: str = "",
    nombre_titular_cti: str = "",
    bastidor_cti: str = "",
    bastidor_anexo_650: str = "",
) -> ResultadoCruce:
    """Cruces de una TRANSFERENCIA por herencia (matriz §9.3).

    Args:
        nombre_causante_defuncion: nombre del fallecido en el certificado de defunción.
        nombre_causante_650:       causante declarado en el modelo 650.
        nombre_titular_cti:        titular del vehículo en el CTI.
        bastidor_cti:              bastidor del CTI.
        bastidor_anexo_650:        bastidor del vehículo en el Anexo 650.
    """
    resultado = ResultadoCruce(tipo_cruce="herencia")

    def _nombres_divergen(a: str, b: str) -> bool:
        return bool(a and b and a.strip().upper() != b.strip().upper())

    # Causante del 650 debe coincidir con el fallecido en defunción
    if _nombres_divergen(nombre_causante_defuncion, nombre_causante_650):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="nombre_causante",
            doc_a="certificado_defuncion",
            valor_a=nombre_causante_defuncion,
            doc_b="modelo_650",
            valor_b=nombre_causante_650,
            severidad=SeveridadCruce.RECHAZADO,
            descripcion=(
                f"El causante del 650 ('{nombre_causante_650}') no coincide con el "
                f"fallecido en el certificado de defunción ('{nombre_causante_defuncion}'). "
                "Cruce de herencia bloqueado."
            ),
        ))

    # Fallecido debe ser el titular del CTI (el vehículo pertenecía al causante)
    if _nombres_divergen(nombre_causante_defuncion, nombre_titular_cti):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="titular_vehiculo",
            doc_a="certificado_defuncion",
            valor_a=nombre_causante_defuncion,
            doc_b="cti",
            valor_b=nombre_titular_cti,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"El fallecido ('{nombre_causante_defuncion}') no coincide con el titular "
                f"del CTI ('{nombre_titular_cti}'). ¿Vehículo a nombre de tercero?"
            ),
        ))

    # El vehículo debe figurar en el Anexo 650 por su bastidor
    if _bastidores_divergen(bastidor_cti, bastidor_anexo_650):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="bastidor",
            doc_a="cti",
            valor_a=bastidor_cti,
            doc_b="anexo_650",
            valor_b=bastidor_anexo_650,
            severidad=SeveridadCruce.RECHAZADO,
            descripcion=(
                f"El bastidor del CTI ({bastidor_cti}) no figura en el Anexo 650 "
                f"({bastidor_anexo_650}). El vehículo no está incluido en la herencia declarada."
            ),
        ))

    return resultado


def cruce_matriculacion(
    bastidor_solicitud: str = "",
    bastidor_ficha_tecnica: str = "",
    bastidor_ivtm: str = "",
    bastidor_impuesto_matriculacion: str = "",
    potencia_kw_ficha: float | None = None,
    potencia_kw_ivtm: float | None = None,
) -> ResultadoCruce:
    """Cruces de una MATRICULACION (matriz §9.4).

    El bastidor debe ser idéntico en todos los documentos de la solicitud.
    La potencia (kW) en la ficha técnica debe coincidir con la base del IVTM.

    Args:
        bastidor_solicitud:               bastidor en la solicitud de matriculación.
        bastidor_ficha_tecnica:           bastidor en la ficha técnica.
        bastidor_ivtm:                    bastidor en el IVTM.
        bastidor_impuesto_matriculacion:  bastidor en el impuesto especial de matriculación.
        potencia_kw_ficha:                potencia en kW de la ficha técnica.
        potencia_kw_ivtm:                 potencia en kW declarada en el IVTM.
    """
    resultado = ResultadoCruce(tipo_cruce="matriculacion")

    # Bastidor consistente entre los cuatro documentos
    fuentes_bastidor = [
        ("solicitud_matriculacion", bastidor_solicitud),
        ("ficha_tecnica", bastidor_ficha_tecnica),
        ("ivtm", bastidor_ivtm),
        ("impuesto_matriculacion", bastidor_impuesto_matriculacion),
    ]
    # Referencia: primer bastidor no vacío
    ref_doc, ref_bastidor = next(
        ((d, b) for d, b in fuentes_bastidor if b),
        (None, ""),
    )
    for doc_nombre, bastidor in fuentes_bastidor:
        if not bastidor or doc_nombre == ref_doc:
            continue
        if _bastidores_divergen(ref_bastidor, bastidor):
            resultado.discrepancias.append(DiscrepanciaCruce(
                campo="bastidor",
                doc_a=ref_doc or "referencia",
                valor_a=ref_bastidor,
                doc_b=doc_nombre,
                valor_b=bastidor,
                severidad=SeveridadCruce.RECHAZADO,
                descripcion=(
                    f"Bastidor en '{doc_nombre}' ({bastidor}) no coincide con "
                    f"'{ref_doc}' ({ref_bastidor}). Expediente de matriculación bloqueado."
                ),
            ))

    # Potencia (kW): ficha técnica vs. base del IVTM
    if potencia_kw_ficha is not None and potencia_kw_ivtm is not None:
        if abs(potencia_kw_ficha - potencia_kw_ivtm) > 0.5:
            resultado.discrepancias.append(DiscrepanciaCruce(
                campo="potencia_kw",
                doc_a="ficha_tecnica",
                valor_a=str(potencia_kw_ficha),
                doc_b="ivtm",
                valor_b=str(potencia_kw_ivtm),
                severidad=SeveridadCruce.EVIDENCIA,
                descripcion=(
                    f"Potencia en ficha técnica ({potencia_kw_ficha} kW) difiere del IVTM "
                    f"({potencia_kw_ivtm} kW). Revisar base de cálculo del impuesto."
                ),
            ))

    return resultado
