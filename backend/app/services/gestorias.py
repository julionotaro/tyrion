"""Mapeo email → nombre legible de gestoría."""
from __future__ import annotations

EMAIL_A_GESTORIA: dict[str, str] = {
    "jlogistic3000@gmail.com":  "Gestoría JLogistic",
    "ruiz@gestorias.es":        "Gestoria Ruiz",
    "lopez@gestorias.es":       "Gestoria López",
    "martin@gestorias.es":      "Gestoria Martín",
    "fernandez@gestorias.es":   "Gestoria Fernández",
    "carballal@gestorias.es":   "Gestoria Carballal",
}


def nombre_gestoria(email: str) -> str:
    """Devuelve el nombre mapeado o un fallback legible (parte antes del @, capitalizada)."""
    email = email.strip().lower()
    if email in EMAIL_A_GESTORIA:
        return EMAIL_A_GESTORIA[email]
    local = email.split("@")[0]
    # quitar puntos/guiones y capitalizar cada palabra
    legible = " ".join(p.capitalize() for p in local.replace(".", " ").replace("-", " ").split())
    return f"Gestoría {legible}"
