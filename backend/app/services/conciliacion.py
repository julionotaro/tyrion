"""Conciliación diaria: planilla × expedientes × hoja de caja.

Cruza tres fuentes por gestoría+día:
  - Planilla (Tempus): universo de trabajo del día.
  - Expedientes (documentación recibida): registro_tramites.
  - Hoja de caja (SAGE): movimientos económicos.

Produce una vista conciliada fila a fila más un cuadre de caja agregado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from app.services.ingesta_planilla import (
    PlanillaDia, _normalizar_bastidor, _normalizar_matricula,
)
from app.services.ingesta_hoja_caja import HojaCaja


# ── Estados ───────────────────────────────────────────────────────────────────

class EstadoConciliacion(str, Enum):
    CUADRADO = "cuadrado"
    PENDIENTE_DOC = "pendiente_doc"
    SIN_EXPEDIENTE = "sin_expediente"
    IMPORTE_DISCREPANTE = "importe_discrepante"
    DUPLICADO = "duplicado"


# Estados de trámite que se consideran "resueltos" (documentación completa)
_ESTADOS_RESUELTOS = frozenset({"listo_dgt", "cerrado", "presentado_dgt"})


# ── Modelos ───────────────────────────────────────────────────────────────────

@dataclass
class FilaConciliada:
    matricula: str
    bastidor: str = ""
    nif_adquirente: str = ""
    nombre_titular: str = ""
    tipo_tramite: str = ""
    num_presentacion: str = ""
    gestoria_nombre: str = ""
    gestoria_email: str = ""
    estado: EstadoConciliacion = EstadoConciliacion.PENDIENTE_DOC
    en_planilla: bool = False
    en_expediente: bool = False
    en_caja: bool = False
    tramite_id: str | None = None
    importe_caja: float = 0.0
    estado_tramite: str = ""
    avisos: list[str] = field(default_factory=list)


@dataclass
class DescuadreCaja:
    total_planilla: int = 0          # nº de filas en planilla
    total_caja: float = 0.0          # suma de importes de caja
    total_expedientes: int = 0       # nº de filas con expediente
    lineas_sin_cruce: list[dict] = field(default_factory=list)   # caja sin planilla
    planilla_sin_caja: list[str] = field(default_factory=list)   # matrículas sin caja


@dataclass
class ConciliacionDia:
    fecha: date
    tipo: str = "TRANSFERENCIA"      # "TRANSFERENCIA" | "MATRICULACION" | "MIXTA"
    filas: list[FilaConciliada] = field(default_factory=list)
    descuadre_caja: DescuadreCaja | None = None
    creado_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total(self) -> int:
        return len(self.filas)

    @property
    def cuadrados(self) -> int:
        return sum(1 for f in self.filas if f.estado == EstadoConciliacion.CUADRADO)

    @property
    def pendientes(self) -> int:
        return sum(1 for f in self.filas if f.estado == EstadoConciliacion.PENDIENTE_DOC)

    @property
    def sin_expediente(self) -> int:
        return sum(1 for f in self.filas if f.estado == EstadoConciliacion.SIN_EXPEDIENTE)


# ── Helpers de cruce ──────────────────────────────────────────────────────────

def _ids_expediente(exp: dict) -> tuple[str, str]:
    """Devuelve (matricula_norm, bastidor_norm) de un expediente."""
    ids = exp.get("identificadores") or {}
    mat = ids.get("matricula") or _normalizar_matricula(exp.get("matricula") or "")
    bas = ids.get("bastidor") or _normalizar_bastidor(exp.get("bastidor") or "")
    return mat, bas


def _buscar_expediente(mat: str, bas: str, expedientes: list[dict]) -> dict | None:
    for exp in expedientes:
        e_mat, e_bas = _ids_expediente(exp)
        if mat and e_mat and mat == e_mat:
            return exp
        if bas and e_bas and bas == e_bas:
            return exp
    return None


# ── Conciliación ──────────────────────────────────────────────────────────────

def conciliar(
    planilla: PlanillaDia,
    expedientes: list[dict],
    hoja_caja: HojaCaja | None = None,
) -> ConciliacionDia:
    """Concilia planilla × expedientes × hoja de caja para un día."""
    conc = ConciliacionDia(
        fecha=planilla.fecha,
        tipo=planilla.tipo.value if hasattr(planilla.tipo, "value") else str(planilla.tipo),
    )

    # Cruce C — detección de duplicados por matrícula en planilla
    conteo_mat: dict[str, int] = {}
    for t in planilla.tramites:
        m = _normalizar_matricula(t.matricula)
        if m:
            conteo_mat[m] = conteo_mat.get(m, 0) + 1

    expedientes_cruzados: set[str] = set()

    for t in planilla.tramites:
        mat = _normalizar_matricula(t.matricula)
        bas = _normalizar_bastidor(t.bastidor)

        fila = FilaConciliada(
            matricula=t.matricula,
            bastidor=t.bastidor,
            nif_adquirente=t.nif_adquirente,
            nombre_titular=t.nombre_titular,
            tipo_tramite=t.tipo_tramite,
            num_presentacion=getattr(t, "num_presentacion", ""),
            en_planilla=True,
        )

        # Cruce A — planilla ↔ expedientes
        exp = _buscar_expediente(mat, bas, expedientes)
        if exp is None:
            fila.estado = EstadoConciliacion.SIN_EXPEDIENTE
            fila.avisos.append(f"No hay expediente para {t.matricula or t.bastidor}")
        else:
            fila.en_expediente = True
            fila.tramite_id = exp.get("id")
            fila.estado_tramite = exp.get("estado") or ""
            fila.gestoria_nombre = exp.get("gestoria") or fila.gestoria_nombre
            fila.gestoria_email = exp.get("gestoria_email") or fila.gestoria_email
            if exp.get("id"):
                expedientes_cruzados.add(exp["id"])
            if fila.estado_tramite in _ESTADOS_RESUELTOS:
                fila.estado = EstadoConciliacion.CUADRADO
            else:
                fila.estado = EstadoConciliacion.PENDIENTE_DOC
                fila.avisos.append(f"Trámite en {fila.estado_tramite or 'estado desconocido'}")

        # Cruce C — duplicado (prevalece sobre lo anterior)
        if mat and conteo_mat.get(mat, 0) > 1:
            fila.estado = EstadoConciliacion.DUPLICADO
            fila.avisos.append(f"Matrícula {t.matricula} duplicada en planilla")

        conc.filas.append(fila)

    # Cruce B — planilla ↔ caja
    if hoja_caja is not None:
        lineas_cruzadas: set[int] = set()
        for fila in conc.filas:
            mat = _normalizar_matricula(fila.matricula)
            lineas = hoja_caja.buscar_por_matricula(mat) if mat else []
            if not lineas and fila.num_presentacion:
                lineas = hoja_caja.buscar_por_num_presentacion(fila.num_presentacion)
            if lineas:
                fila.en_caja = True
                fila.importe_caja = round(sum(l.importe for l in lineas), 2)
                for l in lineas:
                    lineas_cruzadas.add(id(l))
            else:
                fila.avisos.append(f"Sin movimiento en caja para {fila.matricula}")

        # Construir descuadre de caja
        lineas_sin_cruce = [
            {
                "concepto": l.concepto, "importe": l.importe,
                "nif": l.nif, "matricula": l.matricula,
                "num_presentacion": l.num_presentacion,
            }
            for l in hoja_caja.lineas if id(l) not in lineas_cruzadas
        ]
        planilla_sin_caja = [f.matricula for f in conc.filas if not f.en_caja]
        conc.descuadre_caja = DescuadreCaja(
            total_planilla=len(conc.filas),
            total_caja=hoja_caja.total,
            total_expedientes=sum(1 for f in conc.filas if f.en_expediente),
            lineas_sin_cruce=lineas_sin_cruce,
            planilla_sin_caja=planilla_sin_caja,
        )

    return conc
