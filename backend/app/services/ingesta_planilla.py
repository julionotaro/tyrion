"""
Ingesta de la planilla del día (Relación de Transmisiones / Matrículas).

El flujo real arranca en la planilla, no en el email (flujo-operativo §2).
A primera hora el administrativo exporta de Tempus las planillas del día.
Esta planilla es el universo de trabajo cerrado: define qué trámites
deben resolverse. Nada que no esté en la planilla es trabajo del día.

Fuente: docs/flujo-operativo-estandarizado.md §2 + instructivo-operativo §A.1

TODO sesión 8:
  - Parseo de PDF exportado de Tempus (hoy: CSV/texto delimitado)
  - Descarga directa desde Tempus vía API (pendiente confirmar en sesión 2)
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ── Modelos ───────────────────────────────────────────────────────────────────

class TipoPlanilla(str, Enum):
    TRANSMISIONES = "TRANSMISIONES"
    MATRICULAS = "MATRICULAS"


class EstadoTramitePlanificado(str, Enum):
    SIN_DOCUMENTACION = "sin_documentacion"
    CON_DOCUMENTACION = "con_documentacion"
    VALIDADO = "validado"
    ESCALADO = "escalado"


@dataclass
class TramitePlanificado:
    """Una fila de la planilla exportada de Tempus."""
    # Identificadores de cruce (clave primaria = bastidor)
    bastidor: str = ""          # VIN normalizado a mayúsculas sin espacios
    matricula: str = ""
    nif_adquirente: str = ""
    num_expediente: str = ""
    nombre_titular: str = ""
    tipo_tramite: str = ""

    # Estado inicial siempre SIN_DOCUMENTACION hasta que llega el email
    estado: EstadoTramitePlanificado = EstadoTramitePlanificado.SIN_DOCUMENTACION
    tramite_id: str | None = None  # FK a tramites (NULL hasta cruce)

    # Campos adicionales según tipo de planilla
    tasa: str = ""
    razon_social: str = ""
    tipo_transmision: str = ""
    fecha_presentacion: str = ""

    def __post_init__(self):
        self.bastidor = _normalizar_bastidor(self.bastidor)
        self.matricula = _normalizar_matricula(self.matricula)


@dataclass
class PlanillaDia:
    """Planilla completa de un día (TRANSMISIONES o MATRICULAS)."""
    fecha: date
    tipo: TipoPlanilla
    fuente: str = "tempus"   # "tempus" | "manual"
    tramites: list[TramitePlanificado] = field(default_factory=list)
    creado_at: datetime = field(default_factory=datetime.utcnow)

    def __len__(self) -> int:
        return len(self.tramites)

    def buscar_por_bastidor(self, bastidor: str) -> list[TramitePlanificado]:
        b = _normalizar_bastidor(bastidor)
        return [t for t in self.tramites if t.bastidor == b]

    def buscar_por_matricula(self, matricula: str) -> list[TramitePlanificado]:
        m = _normalizar_matricula(matricula)
        return [t for t in self.tramites if t.matricula == m]


# ── Normalización ─────────────────────────────────────────────────────────────

def _normalizar_bastidor(v: str) -> str:
    """VIN normalizado: mayúsculas, sin espacios ni guiones."""
    return v.strip().upper().replace(" ", "").replace("-", "")


def _normalizar_matricula(v: str) -> str:
    return v.strip().upper().replace(" ", "").replace("-", "")


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_relacion_transmisiones(
    contenido: str,
    fecha: date | None = None,
    fuente: str = "tempus",
) -> PlanillaDia:
    """Parsea la Relación de Transmisiones exportada de Tempus.

    Columnas esperadas (CSV delimitado por comas o tabulador):
      num_presentacion, matricula, tasa, adq_nif, razon_social,
      nombre_adquirente, tipo_transmision

    La primera fila puede ser cabecera o datos — se detecta automáticamente.
    El separador se detecta automáticamente (coma o tabulador).
    """
    planilla = PlanillaDia(
        fecha=fecha or date.today(),
        tipo=TipoPlanilla.TRANSMISIONES,
        fuente=fuente,
    )

    reader = _csv_reader(contenido)
    cabecera_detectada = False

    for i, fila in enumerate(reader):
        if not any(fila):
            continue

        # Detectar y saltarse la cabecera
        primera = fila[0].strip().lower()
        if not cabecera_detectada and primera in (
            "num_presentacion", "numpresentacion", "nº", "num", "presentacion", "número"
        ):
            cabecera_detectada = True
            continue

        cabecera_detectada = True  # tras la primera fila no-cabecera, marcamos siempre

        try:
            t = TramitePlanificado(
                num_expediente=_col(fila, 0),
                matricula=_col(fila, 1),
                tasa=_col(fila, 2),
                nif_adquirente=_col(fila, 3),
                razon_social=_col(fila, 4),
                nombre_titular=_col(fila, 5),
                tipo_transmision=_col(fila, 6),
                tipo_tramite="TRANSFERENCIA",
            )
            planilla.tramites.append(t)
        except Exception as exc:
            logger.warning("Fila %d de transmisiones ignorada: %s", i + 1, exc)

    logger.info(
        "Planilla transmisiones %s: %d filas parseadas.",
        planilla.fecha, len(planilla.tramites),
    )
    return planilla


def parse_relacion_matriculas(
    contenido: str,
    fecha: date | None = None,
    fuente: str = "tempus",
) -> PlanillaDia:
    """Parsea la Relación de Matrículas exportada de Tempus.

    Columnas esperadas:
      num_presentacion, matricula, bastidor, apellido1, apellido2,
      nombre, fecha_presentacion
    """
    planilla = PlanillaDia(
        fecha=fecha or date.today(),
        tipo=TipoPlanilla.MATRICULAS,
        fuente=fuente,
    )

    reader = _csv_reader(contenido)
    cabecera_detectada = False

    for i, fila in enumerate(reader):
        if not any(fila):
            continue

        primera = fila[0].strip().lower()
        if not cabecera_detectada and primera in (
            "num_presentacion", "numpresentacion", "nº", "num", "presentacion", "número"
        ):
            cabecera_detectada = True
            continue

        cabecera_detectada = True

        try:
            apellidos = f"{_col(fila, 3)} {_col(fila, 4)}".strip()
            nombre = _col(fila, 5)
            nombre_completo = f"{apellidos}, {nombre}".strip(", ")

            t = TramitePlanificado(
                num_expediente=_col(fila, 0),
                matricula=_col(fila, 1),
                bastidor=_col(fila, 2),
                nombre_titular=nombre_completo,
                fecha_presentacion=_col(fila, 6),
                tipo_tramite="MATRICULACION",
            )
            planilla.tramites.append(t)
        except Exception as exc:
            logger.warning("Fila %d de matrículas ignorada: %s", i + 1, exc)

    logger.info(
        "Planilla matrículas %s: %d filas parseadas.",
        planilla.fecha, len(planilla.tramites),
    )
    return planilla


# ── Helpers internos ──────────────────────────────────────────────────────────

def _csv_reader(contenido: str) -> csv.reader:
    """Detecta el separador y devuelve un lector CSV."""
    sample = contenido[:2000]
    sep = "\t" if sample.count("\t") > sample.count(",") else ","
    return csv.reader(io.StringIO(contenido), delimiter=sep)


def _col(fila: list[str], idx: int) -> str:
    """Extrae una columna de forma segura."""
    if idx < len(fila):
        return fila[idx].strip()
    return ""
