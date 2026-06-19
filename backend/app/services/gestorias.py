"""Store de gestorías en memoria con CRUD completo.

Pre-cargado con las gestorías conocidas como seed. Las gestorías se guardan
indexadas por email normalizado (minúsculas, sin espacios).

Funciones de store: listar(), obtener(email), crear(...), actualizar(...), eliminar(email).
Función de compatibilidad: nombre_gestoria(email) sigue funcionando sobre el store.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Gestoria:
    email: str
    nombre: str
    contacto: str = ""
    telefono: str = ""
    telegram_chat_id: str = ""


# Store mutable en memoria
_STORE: dict[str, Gestoria] = {}

# Seed inicial
_SEED: list[tuple[str, str]] = [
    ("jlogistic3000@gmail.com",  "Gestoría JLogistic"),
    ("ruiz@gestorias.es",        "Gestoria Ruiz"),
    ("lopez@gestorias.es",       "Gestoria López"),
    ("martin@gestorias.es",      "Gestoria Martín"),
    ("fernandez@gestorias.es",   "Gestoria Fernández"),
    ("carballal@gestorias.es",   "Gestoria Carballal"),
]


def _cargar_seed() -> None:
    for email, nombre in _SEED:
        _STORE[email.lower()] = Gestoria(email=email.lower(), nombre=nombre)


_cargar_seed()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def listar() -> list[dict[str, Any]]:
    return [asdict(g) for g in sorted(_STORE.values(), key=lambda g: g.nombre)]


def obtener(email: str) -> dict[str, Any] | None:
    g = _STORE.get(email.strip().lower())
    return asdict(g) if g else None


def crear(
    email: str,
    nombre: str,
    contacto: str = "",
    telefono: str = "",
    telegram_chat_id: str = "",
) -> dict[str, Any]:
    key = email.strip().lower()
    if key in _STORE:
        raise ValueError(f"Gestoría con email '{key}' ya existe.")
    g = Gestoria(
        email=key, nombre=nombre.strip(),
        contacto=contacto, telefono=telefono,
        telegram_chat_id=telegram_chat_id,
    )
    _STORE[key] = g
    return asdict(g)


def actualizar(
    email: str,
    nombre: str | None = None,
    contacto: str | None = None,
    telefono: str | None = None,
    telegram_chat_id: str | None = None,
) -> dict[str, Any]:
    key = email.strip().lower()
    g = _STORE.get(key)
    if g is None:
        raise KeyError(f"Gestoría '{key}' no encontrada.")
    if nombre is not None:
        g.nombre = nombre.strip()
    if contacto is not None:
        g.contacto = contacto
    if telefono is not None:
        g.telefono = telefono
    if telegram_chat_id is not None:
        g.telegram_chat_id = telegram_chat_id
    return asdict(g)


def obtener_por_telegram_chat_id(chat_id: str) -> dict[str, Any] | None:
    """Devuelve la gestoría registrada con ese chat_id de Telegram, o None."""
    for g in _STORE.values():
        if g.telegram_chat_id and g.telegram_chat_id == chat_id:
            return asdict(g)
    return None


def eliminar(email: str) -> bool:
    key = email.strip().lower()
    if key not in _STORE:
        raise KeyError(f"Gestoría '{key}' no encontrada.")
    del _STORE[key]
    return True


def reset() -> None:
    """Restaura el seed. Solo para tests."""
    _STORE.clear()
    _cargar_seed()


# ── Compatibilidad ────────────────────────────────────────────────────────────

# Alias de compatibilidad para tests legacy
EMAIL_A_GESTORIA: dict[str, str] = {e: n for e, n in _SEED}


def nombre_gestoria(email: str) -> str:
    """Devuelve el nombre mapeado o un fallback legible (parte antes del @, capitalizada)."""
    key = email.strip().lower()
    g = _STORE.get(key)
    if g:
        return g.nombre
    local = key.split("@")[0]
    legible = " ".join(p.capitalize() for p in local.replace(".", " ").replace("-", " ").split())
    return f"Gestoría {legible}"
