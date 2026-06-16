"""
Cruce email↔planilla — Fase 3 del flujo operativo.

Cada email entrante se cruza contra la fila correspondiente de la planilla
del día. Clave primaria: bastidor (VIN). Claves secundarias: matrícula,
NIF adquirente, nº expediente.

Fuente: docs/flujo-operativo-estandarizado.md §4

Regla de negocio: emails sin match NO se descartan (pueden llegar antes que
la planilla esté cargada). Se registran como pendiente_revision y se
re-intentan cuando llegue la planilla.

TODO sesión 8:
  - Re-intentar cruce de emails sin_match cuando se cargue una nueva planilla
  - Notificar al administrativo de emails que llevan >N horas sin match
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.ingesta_planilla import PlanillaDia, TramitePlanificado, _normalizar_bastidor


class ConfianzaCruce(str, Enum):
    ALTA = "ALTA"       # bastidor exacto (17 caracteres)
    MEDIA = "MEDIA"     # últimos 4 dígitos del bastidor, o matrícula exacta
    BAJA = "BAJA"       # NIF adquirente (puede coincidir en varios trámites)
    NINGUNA = "NINGUNA" # sin match


class MetodoCruce(str, Enum):
    BASTIDOR_EXACTO = "bastidor_exacto"
    BASTIDOR_4DIG = "bastidor_4dig"
    MATRICULA = "matricula"
    NIF = "nif"
    SIN_MATCH = "sin_match"


@dataclass
class CruceResult:
    """Resultado del intento de cruce de un email con la planilla del día."""
    tramite_planificado: TramitePlanificado | None
    confianza: ConfianzaCruce
    metodo: MetodoCruce
    candidatos: int = 0       # número de filas que cumplían el criterio (útil si >1)
    ambiguo: bool = False     # True si hay más de un candidato con igual confianza

    @property
    def tiene_match(self) -> bool:
        return self.tramite_planificado is not None


def cruzar_email_con_planilla(
    bastidor_email: str = "",
    matricula_email: str = "",
    nif_email: str = "",
    planilla: PlanillaDia | None = None,
) -> CruceResult:
    """Intenta cruzar los datos extraídos de un email con la planilla del día.

    Orden de búsqueda (mayor a menor confianza):
      1. Bastidor exacto (17 caracteres) → ALTA
      2. Últimos 4 dígitos del bastidor  → MEDIA
      3. Matrícula exacta                → MEDIA
      4. NIF del adquirente              → BAJA
      Sin match                          → NINGUNA

    El primer nivel que encuentra al menos un resultado gana.
    Si hay múltiples candidatos en el mismo nivel → ambiguo=True,
    se devuelve el primero y se registra para revisión humana.

    Args:
        bastidor_email:  bastidor extraído del email/documentos adjuntos.
        matricula_email: matrícula extraída del email.
        nif_email:       NIF del adquirente extraído.
        planilla:        planilla del día contra la que cruzar.
                         Si es None → sin_match inmediato.
    """
    if not planilla or not planilla.tramites:
        return CruceResult(
            tramite_planificado=None,
            confianza=ConfianzaCruce.NINGUNA,
            metodo=MetodoCruce.SIN_MATCH,
        )

    # 1. Bastidor exacto
    if bastidor_email:
        b_norm = _normalizar_bastidor(bastidor_email)
        if b_norm:
            candidatos = planilla.buscar_por_bastidor(b_norm)
            if candidatos:
                return CruceResult(
                    tramite_planificado=candidatos[0],
                    confianza=ConfianzaCruce.ALTA,
                    metodo=MetodoCruce.BASTIDOR_EXACTO,
                    candidatos=len(candidatos),
                    ambiguo=len(candidatos) > 1,
                )

    # 2. Últimos 4 dígitos del bastidor
    if bastidor_email:
        b_norm = _normalizar_bastidor(bastidor_email)
        if len(b_norm) >= 4:
            sufijo = b_norm[-4:]
            candidatos = [
                t for t in planilla.tramites
                if t.bastidor and t.bastidor[-4:] == sufijo
            ]
            if candidatos:
                return CruceResult(
                    tramite_planificado=candidatos[0],
                    confianza=ConfianzaCruce.MEDIA,
                    metodo=MetodoCruce.BASTIDOR_4DIG,
                    candidatos=len(candidatos),
                    ambiguo=len(candidatos) > 1,
                )

    # 3. Matrícula exacta
    if matricula_email:
        from app.services.ingesta_planilla import _normalizar_matricula
        m_norm = _normalizar_matricula(matricula_email)
        if m_norm:
            candidatos = planilla.buscar_por_matricula(m_norm)
            if candidatos:
                return CruceResult(
                    tramite_planificado=candidatos[0],
                    confianza=ConfianzaCruce.MEDIA,
                    metodo=MetodoCruce.MATRICULA,
                    candidatos=len(candidatos),
                    ambiguo=len(candidatos) > 1,
                )

    # 4. NIF adquirente
    if nif_email:
        nif_norm = nif_email.strip().upper()
        candidatos = [
            t for t in planilla.tramites
            if t.nif_adquirente and t.nif_adquirente.upper() == nif_norm
        ]
        if candidatos:
            return CruceResult(
                tramite_planificado=candidatos[0],
                confianza=ConfianzaCruce.BAJA,
                metodo=MetodoCruce.NIF,
                candidatos=len(candidatos),
                ambiguo=len(candidatos) > 1,
            )

    # Sin match
    return CruceResult(
        tramite_planificado=None,
        confianza=ConfianzaCruce.NINGUNA,
        metodo=MetodoCruce.SIN_MATCH,
    )
