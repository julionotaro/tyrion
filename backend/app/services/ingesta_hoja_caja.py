"""Ingesta de la Hoja de Caja diaria exportada de SAGE."""
from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

logger = logging.getLogger(__name__)


# ── Modelos ───────────────────────────────────────────────────────────────────

@dataclass
class LineaCaja:
    fecha: str
    concepto: str
    importe: float
    nif: str = ""
    matricula: str = ""
    num_presentacion: str = ""
    fuente: str = "sage"


@dataclass
class HojaCaja:
    fecha: date
    gestoria_email: str = ""
    lineas: list[LineaCaja] = field(default_factory=list)
    creado_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total(self) -> float:
        return round(sum(l.importe for l in self.lineas), 2)

    def buscar_por_matricula(self, matricula: str) -> list[LineaCaja]:
        m = _normalizar(matricula)
        return [l for l in self.lineas if _normalizar(l.matricula) == m and m]

    def buscar_por_nif(self, nif: str) -> list[LineaCaja]:
        n = _normalizar(nif)
        return [l for l in self.lineas if _normalizar(l.nif) == n and n]

    def buscar_por_num_presentacion(self, num: str) -> list[LineaCaja]:
        n = (num or "").strip()
        return [l for l in self.lineas if l.num_presentacion == n and n]


# Mapa de conceptos de caja a familia documental
MAPA_CAJA_A_FAMILIA: dict[str, str] = {
    "TRANSFERENCIA": "TRANSFERENCIA",
    "TRANSMISION": "TRANSFERENCIA",
    "MATRICULACION": "MATRICULACION",
    "MATRICULA": "MATRICULACION",
    "BAJA": "BAJA",
}


# ── Patrones ──────────────────────────────────────────────────────────────────

_PAT_FECHA = re.compile(r'\b(\d{2})/(\d{2})/(\d{4})\b')
_PAT_IMPORTE = re.compile(r'\d+[.,]\d{2}')
_PAT_NIF = re.compile(r'\b(\d{8}[A-Za-z])\b')
_PAT_MATRICULA = re.compile(r'\b(\d{4}\s?[A-Za-z]{3}|[A-Za-z]{1,2}\d{3,4}[A-Za-z]{1,2})\b')
_PAT_NUM_PRESENTACION = re.compile(r'\b(\d{5})\b')


def _normalizar(v: str) -> str:
    return (v or "").strip().upper().replace(" ", "").replace("-", "")


def _fecha_desde_texto(texto: str) -> date | None:
    m = _PAT_FECHA.search(texto)
    if not m:
        return None
    try:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    except (ValueError, TypeError):
        return None


def clasificar_concepto(concepto: str) -> str:
    """Devuelve la familia documental para un concepto de caja, o "" si no mapea."""
    up = (concepto or "").upper()
    for clave, familia in MAPA_CAJA_A_FAMILIA.items():
        if clave in up:
            return familia
    return ""


# ── Parser PDF (best-effort) ────────────────────────────────────────────────────

def parse_hoja_caja_pdf(
    contenido: bytes,
    fecha: date | None = None,
    gestoria_email: str = "",
) -> HojaCaja:
    """Parsea la Hoja de Caja en PDF exportada de SAGE (best-effort)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) no instalado — no se puede parsear PDF de caja.")
        texto = ""
    else:
        texto = ""
        try:
            doc = fitz.open(stream=contenido, filetype="pdf")
            for page in doc:
                texto += page.get_text() + "\n"
            doc.close()
        except Exception as exc:
            logger.error("Error abriendo PDF de hoja de caja: %s", exc)
            texto = ""

    hoja = HojaCaja(
        fecha=fecha or _fecha_desde_texto(texto) or date.today(),
        gestoria_email=gestoria_email,
    )

    for linea in texto.splitlines():
        m_imp = list(_PAT_IMPORTE.finditer(linea))
        if not m_imp:
            continue
        # El último importe de la línea se considera el importe de la operación
        match_imp = m_imp[-1]
        try:
            importe = float(match_imp.group(0).replace(".", "").replace(",", ".")) \
                if "," in match_imp.group(0) else float(match_imp.group(0))
        except ValueError:
            continue

        concepto = linea[:match_imp.start()].strip()
        nif_m = _PAT_NIF.search(linea)
        mat_m = _PAT_MATRICULA.search(linea)
        np_m = _PAT_NUM_PRESENTACION.search(linea)

        hoja.lineas.append(LineaCaja(
            fecha=hoja.fecha.isoformat(),
            concepto=concepto,
            importe=importe,
            nif=nif_m.group(1) if nif_m else "",
            matricula=mat_m.group(1).strip() if mat_m else "",
            num_presentacion=np_m.group(1) if np_m else "",
        ))

    logger.info("Hoja de caja PDF %s: %d líneas.", hoja.fecha, len(hoja.lineas))
    return hoja


# ── Parser CSV ──────────────────────────────────────────────────────────────────

def parse_hoja_caja_csv(
    contenido: str,
    fecha: date | None = None,
    gestoria_email: str = "",
) -> HojaCaja:
    """Parsea la Hoja de Caja en CSV.

    Columnas: fecha,concepto,importe,nif,matricula,num_presentacion
    """
    hoja = HojaCaja(
        fecha=fecha or _fecha_desde_texto(contenido) or date.today(),
        gestoria_email=gestoria_email,
    )

    sample = contenido[:2000]
    sep = "\t" if sample.count("\t") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(contenido), delimiter=sep)
    cabecera_detectada = False

    for fila in reader:
        if not any(c.strip() for c in fila):
            continue
        primera = fila[0].strip().lower()
        if not cabecera_detectada and primera in ("fecha", "concepto"):
            cabecera_detectada = True
            continue
        cabecera_detectada = True

        def _c(i: int) -> str:
            return fila[i].strip() if i < len(fila) else ""

        importe_raw = _c(2)
        try:
            importe = float(importe_raw.replace(".", "").replace(",", ".")) \
                if "," in importe_raw else float(importe_raw or 0)
        except ValueError:
            importe = 0.0

        hoja.lineas.append(LineaCaja(
            fecha=_c(0),
            concepto=_c(1),
            importe=importe,
            nif=_c(3),
            matricula=_c(4),
            num_presentacion=_c(5),
        ))

    logger.info("Hoja de caja CSV %s: %d líneas.", hoja.fecha, len(hoja.lineas))
    return hoja
