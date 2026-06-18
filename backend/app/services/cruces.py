"""
Validaciones cruzadas multi-documento de Tyrion.

Implementa los cruces de la matriz §9 (docs/matriz-documental-tramites.md):
  - cruce_transferencia(): CET del CTI == CET del 620; bastidores consistentes
  - cruce_herencia():      matrícula consistente (CTI + declaración + anexo 650);
                           identidad causante y heredero por DNI;
                           bastidor presente en anexo 650 (no se cruza con otro doc)
  - cruce_matriculacion(): bastidor consistente en solicitud + ficha + IVTM +
                           impuesto matriculación

Cotejo herencia confirmado con administrativo (sesión 13):
  - El CTI NO lleva bastidor en herencia; la MATRÍCULA es la clave de cruce.
  - Los cruces de identidad usan DNI (más confiable que nombre).
  - El bastidor solo existe en el anexo 650; se valida presencia, no cruce.

Clave de cruce primaria = BASTIDOR en transferencia ordinaria y matriculación.
En HERENCIA la clave central es la MATRÍCULA.
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
    matricula_cti: str = "",
    matricula_declaracion: str = "",
    matricula_anexo_650: str = "",
    dni_causante_defuncion: str = "",
    dni_causante_650: str = "",
    dni_transmitente_cti: str = "",
    dni_heredero_declaracion: str = "",
    dni_heredero_650: str = "",
    dni_adquirente_cti: str = "",
    bastidor_anexo_650: str = "",
) -> ResultadoCruce:
    """Cruces de una TRANSFERENCIA por herencia.

    Cotejo real confirmado con administrativo (sesión 13):
      - Clave central: MATRÍCULA coincide en CTI + declaración responsable + anexo 650.
        (El CTI NO lleva bastidor; la matrícula es la clave de cruce en herencia.)
      - Identidad del causante (por DNI): certificado defunción == modelo 650 == transmitente CTI.
      - Identidad del heredero (por DNI): declaración == modelo 650 (sujeto pasivo) == adquirente CTI.
      - Bastidor del anexo 650: se valida "presente y legible", NO se cruza contra otro
        documento (el bastidor solo figura en el anexo en una herencia).
        El cruce bastidor↔documento de tasa se reserva para trámites con pago de tasa.
    """
    resultado = ResultadoCruce(tipo_cruce="herencia")

    def _difieren(a: str, b: str) -> bool:
        return bool(a and b and a.strip().upper().replace("-", "").replace(" ", "")
                    != b.strip().upper().replace("-", "").replace(" ", ""))

    # ── Cruce 1: MATRÍCULA (clave central) ──
    # CTI ↔ declaración responsable
    if _difieren(matricula_cti, matricula_declaracion):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="matricula",
            doc_a="cti", valor_a=matricula_cti,
            doc_b="declaracion_responsable_fallecimiento", valor_b=matricula_declaracion,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"La matrícula del CTI ({matricula_cti}) no coincide con la de la "
                f"declaración responsable ({matricula_declaracion}). Pedir aclaración a gestoría."
            ),
        ))
    # CTI ↔ anexo 650
    if _difieren(matricula_cti, matricula_anexo_650):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="matricula",
            doc_a="cti", valor_a=matricula_cti,
            doc_b="anexo_650", valor_b=matricula_anexo_650,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"La matrícula del CTI ({matricula_cti}) no figura en el Anexo 650 "
                f"({matricula_anexo_650}). Verificar que el vehículo está incluido en la herencia."
            ),
        ))

    # ── Cruce 2: Identidad del CAUSANTE (por DNI) ──
    # defunción ↔ modelo 650
    if _difieren(dni_causante_defuncion, dni_causante_650):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="dni_causante",
            doc_a="certificado_defuncion", valor_a=dni_causante_defuncion,
            doc_b="modelo_650", valor_b=dni_causante_650,
            severidad=SeveridadCruce.RECHAZADO,
            descripcion=(
                f"El DNI del causante en el modelo 650 ({dni_causante_650}) no coincide "
                f"con el fallecido del certificado de defunción ({dni_causante_defuncion}). "
                "Cruce de herencia bloqueado."
            ),
        ))
    # defunción ↔ transmitente CTI
    if _difieren(dni_causante_defuncion, dni_transmitente_cti):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="dni_causante",
            doc_a="certificado_defuncion", valor_a=dni_causante_defuncion,
            doc_b="cti", valor_b=dni_transmitente_cti,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"El DNI del fallecido ({dni_causante_defuncion}) no coincide con el "
                f"transmitente del CTI ({dni_transmitente_cti}). ¿Vehículo a nombre de tercero?"
            ),
        ))

    # ── Cruce 3: Identidad del HEREDERO/adquirente (por DNI) ──
    # declaración ↔ modelo 650 sujeto pasivo
    if _difieren(dni_heredero_declaracion, dni_heredero_650):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="dni_heredero",
            doc_a="declaracion_responsable_fallecimiento", valor_a=dni_heredero_declaracion,
            doc_b="modelo_650", valor_b=dni_heredero_650,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"El DNI del declarante ({dni_heredero_declaracion}) no coincide con el "
                f"sujeto pasivo del modelo 650 ({dni_heredero_650}). Pedir aclaración."
            ),
        ))
    # declaración ↔ adquirente CTI
    if _difieren(dni_heredero_declaracion, dni_adquirente_cti):
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="dni_heredero",
            doc_a="declaracion_responsable_fallecimiento", valor_a=dni_heredero_declaracion,
            doc_b="cti", valor_b=dni_adquirente_cti,
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                f"El DNI del declarante ({dni_heredero_declaracion}) no coincide con el "
                f"adquirente del CTI ({dni_adquirente_cti})."
            ),
        ))

    # ── Validación 4: bastidor presente en anexo 650 (NO se cruza) ──
    if not bastidor_anexo_650 or not bastidor_anexo_650.strip():
        resultado.discrepancias.append(DiscrepanciaCruce(
            campo="bastidor",
            doc_a="anexo_650", valor_a="(ausente)",
            doc_b="anexo_650", valor_b="(ausente)",
            severidad=SeveridadCruce.EVIDENCIA,
            descripcion=(
                "No se pudo extraer el bastidor del vehículo en el Anexo 650. "
                "El bastidor es obligatorio para la presentación a DGT. Pedir reenvío legible."
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

