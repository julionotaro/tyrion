"""Templates de avisos salientes: aviso_1, aviso_2, escalado_admin."""
from __future__ import annotations


def _html_wrapper(titulo: str, cuerpo_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:24px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e0e0e0;">
      <tr>
        <td style="background:#0F6E56;padding:24px 32px;">
          <span style="color:#ffffff;font-size:20px;font-weight:bold;">Tyrion</span>
          <span style="color:#a7d9cc;font-size:14px;margin-left:12px;">Colegio de Gestores de Pontevedra</span>
        </td>
      </tr>
      <tr>
        <td style="padding:32px;">
          <h2 style="color:#1A2E2A;margin:0 0 16px;">{titulo}</h2>
          {cuerpo_html}
          <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
          <p style="color:#8A9E9A;font-size:12px;margin:0;">
            Tyrion · Colegio de Gestores de Pontevedra<br>
            Mensaje automático — no responda a este correo directamente.
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _lista_requisitos(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(
        f'<li style="margin:4px 0;color:#1A2E2A;">{r.replace("_", " ").capitalize()}</li>'
        for r in items
    )
    return f'<ul style="padding-left:20px;margin:8px 0;">{lis}</ul>'


def aviso_1(
    matricula: str,
    gestoria: str,
    requisitos_faltantes: list[str],
    requisitos_evidencia: list[str],
) -> tuple[str, str, str]:
    """T+0: primer aviso de documentación pendiente."""
    asunto = f"[Tyrion] Documentación pendiente — {matricula}"

    pendientes = requisitos_faltantes + requisitos_evidencia
    lista_html = _lista_requisitos(pendientes)
    lista_texto = "\n".join(f"  • {r.replace('_', ' ')}" for r in pendientes)

    cuerpo_html = f"""
<p style="color:#1A2E2A;">Estimada gestoría <strong>{gestoria}</strong>,</p>
<p style="color:#4A5E5A;">
  Hemos revisado la documentación recibida para el vehículo <strong>{matricula}</strong>
  y necesitamos que completen el expediente con los siguientes documentos:
</p>
{lista_html}
<p style="color:#4A5E5A;">
  Rogamos que envíen la documentación a la mayor brevedad para poder completar el trámite
  dentro del plazo del día.
</p>
"""
    cuerpo_texto = f"""Estimada gestoría {gestoria},

Hemos revisado la documentación recibida para el vehículo {matricula}
y necesitamos que completen el expediente con los siguientes documentos:

{lista_texto}

Rogamos que envíen la documentación a la mayor brevedad.

Tyrion · Colegio de Gestores de Pontevedra"""

    return asunto, _html_wrapper("Documentación pendiente", cuerpo_html), cuerpo_texto


def aviso_2(
    matricula: str,
    gestoria: str,
    requisitos_faltantes: list[str],
) -> tuple[str, str, str]:
    """T+30: recordatorio."""
    asunto = f"[Tyrion] Recordatorio — {matricula}"

    lista_html = _lista_requisitos(requisitos_faltantes)
    lista_texto = "\n".join(f"  • {r.replace('_', ' ')}" for r in requisitos_faltantes)

    cuerpo_html = f"""
<p style="color:#1A2E2A;">Estimada gestoría <strong>{gestoria}</strong>,</p>
<p style="color:#4A5E5A;">
  Les recordamos que el expediente del vehículo <strong>{matricula}</strong>
  sigue pendiente de la siguiente documentación:
</p>
{lista_html}
<p style="color:#4A5E5A;">
  Si no recibimos la documentación en breve, el expediente deberá ser escalado
  al administrativo para su resolución.
</p>
"""
    cuerpo_texto = f"""Estimada gestoría {gestoria},

Les recordamos que el expediente del vehículo {matricula}
sigue pendiente de la siguiente documentación:

{lista_texto}

Si no recibimos la documentación en breve, el expediente deberá escalarse.

Tyrion · Colegio de Gestores de Pontevedra"""

    return asunto, _html_wrapper("Recordatorio de documentación", cuerpo_html), cuerpo_texto


def escalado_admin(
    matricula: str,
    gestoria: str,
    tramite_id: str,
    requisitos_faltantes: list[str],
) -> tuple[str, str, str]:
    """T+60: escalado al administrativo."""
    asunto = f"[Tyrion] Escalado administrativo — {matricula}"

    lista_html = _lista_requisitos(requisitos_faltantes)
    lista_texto = "\n".join(f"  • {r.replace('_', ' ')}" for r in requisitos_faltantes)

    cuerpo_html = f"""
<p style="color:#1A2E2A;"><strong>Escalado para revisión manual</strong></p>
<p style="color:#4A5E5A;">
  El expediente del vehículo <strong>{matricula}</strong> (gestoría: {gestoria},
  ID: <code>{tramite_id}</code>) no ha recibido la documentación solicitada
  tras dos avisos. Requiere intervención del administrativo.
</p>
<p style="color:#4A5E5A;">Documentación pendiente:</p>
{lista_html}
"""
    cuerpo_texto = f"""Escalado para revisión manual

Vehículo: {matricula}
Gestoría: {gestoria}
ID trámite: {tramite_id}

Documentación pendiente:
{lista_texto}

El expediente no ha recibido respuesta tras dos avisos.
Requiere intervención manual.

Tyrion · Colegio de Gestores de Pontevedra"""

    return asunto, _html_wrapper("Escalado administrativo", cuerpo_html), cuerpo_texto
