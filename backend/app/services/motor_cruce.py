"""Motor de cruce declarativo: coteja datos entre documentos de un trámite."""
from __future__ import annotations
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Criticidad(str, Enum):
    CRITICA = "CRITICA"
    ADVERTENCIA = "ADVERTENCIA"


@dataclass
class ReglaCruce:
    tipo_a: str
    campo_a: str
    tipo_b: str
    campo_b: str
    label: str
    criticidad: Criticidad = Criticidad.CRITICA
    normalizador: str = "texto"


# ── Normalizadores puros ──────────────────────────────────────────────────────

def _norm_texto(v: str) -> str:
    return " ".join(v.strip().upper().split())

def _norm_documento_id(v: str) -> str:
    return v.strip().replace(" ", "").replace("-", "").replace(".", "").upper()

def _norm_matricula(v: str) -> str:
    return v.strip().replace(" ", "").replace("-", "").upper()

def _norm_bastidor(v: str) -> str:
    return v.strip().replace(" ", "").upper()

_NORMALIZADORES: dict[str, Any] = {
    "texto": _norm_texto,
    "documento_id": _norm_documento_id,
    "matricula": _norm_matricula,
    "bastidor": _norm_bastidor,
}


# ── Matching de nombres tolerante ─────────────────────────────────────────────

def _tokens_nombre(v: str | None) -> list[str]:
    s = "".join(
        c for c in unicodedata.normalize("NFKD", v or "")
        if not unicodedata.combining(c)
    )
    s = s.upper().replace(".", " ")
    return [t for t in s.split() if t]


def _coincide_nombre(a: str | None, b: str | None) -> bool:
    ta, tb = _tokens_nombre(a), _tokens_nombre(b)
    if not ta or not tb:
        return False
    corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # Ordenar por longitud descendente: tokens largos (específicos) se asignan primero,
    # evitando que una inicial ("C") consuma un token largo ("CARBALLAL") de forma codiciosa.
    corto_ordenado = sorted(corto, key=len, reverse=True)
    usados: list[str] = []
    for t in corto_ordenado:
        m = next(
            (u for u in largo if u not in usados and
             (u == t or u.startswith(t) or t.startswith(u))),
            None,
        )
        if m is None:
            return False
        usados.append(m)
    return True


# ── Tabla de reglas por (familia, subtipo) ────────────────────────────────────

C = Criticidad

REGLAS_CRUCE: dict[tuple[str, str], list[ReglaCruce]] = {
    ("TRANSFERENCIA", "ninguno"): [
        ReglaCruce("cti", "matricula", "modelo_620", "matricula", "Matrícula", C.CRITICA, "matricula"),
        ReglaCruce("cti", "dni_adquirente", "modelo_620", "nif_adquirente", "DNI adquirente", C.CRITICA, "documento_id"),
        ReglaCruce("cti", "dni_transmitente", "modelo_620", "nif_transmitente", "DNI transmitente", C.CRITICA, "documento_id"),
        ReglaCruce("cti", "bastidor", "modelo_620", "bastidor", "Bastidor", C.CRITICA, "bastidor"),
        ReglaCruce("cti", "nombre_adquirente", "modelo_620", "nombre_adquirente", "Nombre adquirente", C.ADVERTENCIA, "nombre"),
        ReglaCruce("cti", "nombre_transmitente", "modelo_620", "nombre_transmitente", "Nombre transmitente", C.ADVERTENCIA, "nombre"),
        ReglaCruce("cti", "cet", "modelo_620", "cet", "CET", C.ADVERTENCIA, "texto"),
    ],
    ("TRANSFERENCIA", "herencia"): [
        ReglaCruce("declaracion_responsable_fallecimiento", "matricula", "anexo_650", "matricula", "Matrícula", C.CRITICA, "matricula"),
        ReglaCruce("declaracion_responsable_fallecimiento", "dni", "modelo_650", "dni_sujeto_pasivo", "DNI heredero", C.CRITICA, "documento_id"),
        ReglaCruce("modelo_650", "dni_causante", "certificado_defuncion", "dni_fallecido", "DNI causante", C.CRITICA, "documento_id"),
        ReglaCruce("modelo_650", "matricula", "anexo_650", "matricula", "Matrícula (650/anexo)", C.CRITICA, "matricula"),
        ReglaCruce("declaracion_responsable_fallecimiento", "nombre", "modelo_650", "nombre_sujeto_pasivo", "Nombre heredero", C.ADVERTENCIA, "nombre"),
        ReglaCruce("modelo_650", "nombre_causante", "certificado_defuncion", "nombre_fallecido", "Nombre causante", C.ADVERTENCIA, "nombre"),
    ],
    ("MATRICULACION", "ninguno"): [],  # TODO pendiente confirmación administrativa
    ("BAJA", "ninguno"): [],           # TODO pendiente confirmación administrativa
}


# ── Función principal ─────────────────────────────────────────────────────────

def cotejar_datos(
    familia: str,
    subtipo: str,
    docs_por_tipo: dict[str, dict],
) -> list[dict]:
    """Coteja datos entre documentos según las reglas de (familia, subtipo).

    docs_por_tipo: {tipo_documento: datos_extraidos_dict}

    Devuelve lista de verificaciones con campos:
      campo, label, ok, estado, criticidad, vals, aviso (solo si discrepancia).
    """
    reglas = REGLAS_CRUCE.get((familia, subtipo), [])
    resultado: list[dict] = []

    for r in reglas:
        if r.tipo_a not in docs_por_tipo or r.tipo_b not in docs_por_tipo:
            continue  # documento no recibido → regla no aplica

        val_a = docs_por_tipo[r.tipo_a].get(r.campo_a) or None
        val_b = docs_por_tipo[r.tipo_b].get(r.campo_b) or None

        campo_key = f"{r.tipo_a}_{r.campo_a}__{r.tipo_b}_{r.campo_b}"
        base: dict = {
            "campo": campo_key,
            "label": r.label,
            "criticidad": r.criticidad.value,
            "vals": [
                {"doc": r.tipo_a, "val": val_a},
                {"doc": r.tipo_b, "val": val_b},
            ],
        }

        if val_a is None or val_b is None:
            base.update({"ok": False, "estado": "incompleto"})
        else:
            if r.normalizador == "nombre":
                coincide = _coincide_nombre(val_a, val_b)
            else:
                fn = _NORMALIZADORES.get(r.normalizador, _norm_texto)
                coincide = fn(val_a) == fn(val_b)

            if coincide:
                base.update({"ok": True, "estado": "ok"})
            else:
                base.update({
                    "ok": False,
                    "estado": "discrepancia",
                    "aviso": f"{r.label} no coincide entre {r.tipo_a} ({val_a}) y {r.tipo_b} ({val_b}).",
                })

        resultado.append(base)

    return resultado
