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
import re
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
    num_presentacion: str = ""
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
                num_presentacion=_col(fila, 0),
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
                num_presentacion=_col(fila, 0),
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


# ── Parser PDF (best-effort, basado en tokens) ──────────────────────────────────

_PAT_FECHA = re.compile(r'\b(\d{2})/(\d{2})/(\d{4})\b')
_PAT_NUM_PRESENTACION = re.compile(r'^\d{4,6}$')


def _fecha_desde_texto(texto: str) -> date | None:
    m = _PAT_FECHA.search(texto)
    if not m:
        return None
    try:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    except (ValueError, TypeError):
        return None


def parse_planilla_pdf(
    contenido: bytes,
    fecha: date | None = None,
    fuente: str = "tempus",
) -> PlanillaDia:
    """Parsea una planilla PDF exportada de Tempus (best-effort, basado en tokens).

    Detecta el tipo por cabecera (TRANSMISIONES / MATRICULAS), extrae la fecha si
    no se proporciona, y parsea las filas dividiendo cada línea en tokens. Si el
    primer token es un índice numérico de fila, se interpreta el resto como datos.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) no instalado — no se puede parsear PDF.")
        texto = ""
    else:
        texto = ""
        try:
            doc = fitz.open(stream=contenido, filetype="pdf")
            for page in doc:
                texto += page.get_text() + "\n"
            doc.close()
        except Exception as exc:
            logger.error("Error abriendo PDF de planilla: %s", exc)
            texto = ""

    texto_up = texto.upper()
    if "MATRICULA" in texto_up and "TRANSMISION" not in texto_up:
        tipo = TipoPlanilla.MATRICULAS
    elif "TRANSMISION" in texto_up:
        tipo = TipoPlanilla.TRANSMISIONES
    else:
        # Default a transmisiones (caso mayoritario)
        tipo = TipoPlanilla.TRANSMISIONES

    planilla = PlanillaDia(
        fecha=fecha or _fecha_desde_texto(texto) or date.today(),
        tipo=tipo,
        fuente=fuente,
    )

    for linea in texto.splitlines():
        tokens = linea.split()
        if not tokens:
            continue
        # La primera columna debe ser un índice de fila numérico
        if not tokens[0].isdigit():
            continue
        datos = tokens[1:]
        if not datos:
            continue
        # Buscar el número de presentación (primer token de 4-6 dígitos)
        if not _PAT_NUM_PRESENTACION.match(datos[0]):
            continue
        try:
            if tipo == TipoPlanilla.TRANSMISIONES:
                # num_presentacion, matricula, tasa, nif, nombre...
                num_pres = datos[0]
                matricula = datos[1] if len(datos) > 1 else ""
                tasa = datos[2] if len(datos) > 2 else ""
                nif = datos[3] if len(datos) > 3 else ""
                nombre = " ".join(datos[4:]) if len(datos) > 4 else ""
                t = TramitePlanificado(
                    num_expediente=num_pres,
                    num_presentacion=num_pres,
                    matricula=matricula,
                    tasa=tasa,
                    nif_adquirente=nif,
                    nombre_titular=nombre,
                    tipo_tramite="TRANSFERENCIA",
                )
            else:
                # num_presentacion, matricula, bastidor, nombre..., fecha
                num_pres = datos[0]
                matricula = datos[1] if len(datos) > 1 else ""
                bastidor = datos[2] if len(datos) > 2 else ""
                fecha_pres = ""
                resto = datos[3:]
                if resto and _PAT_FECHA.match(resto[-1]):
                    fecha_pres = resto[-1]
                    resto = resto[:-1]
                nombre = " ".join(resto)
                t = TramitePlanificado(
                    num_expediente=num_pres,
                    num_presentacion=num_pres,
                    matricula=matricula,
                    bastidor=bastidor,
                    nombre_titular=nombre,
                    fecha_presentacion=fecha_pres,
                    tipo_tramite="MATRICULACION",
                )
            planilla.tramites.append(t)
        except Exception as exc:
            logger.warning("Línea de planilla PDF ignorada (%r): %s", linea, exc)

    logger.info(
        "Planilla PDF %s (%s): %d filas parseadas.",
        planilla.fecha, tipo.value, len(planilla.tramites),
    )
    return planilla
