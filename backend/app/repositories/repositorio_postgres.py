"""
Implementación PostgreSQL de RepositorioPipeline.

Usa psycopg2 (síncrono) con la misma interfaz que RepositorioEnMemoria,
permitiendo intercambio transparente según USE_DATOS_PRUEBA.

Conexión desde DATABASE_URL en settings. Se admite tanto el formato asyncpg
(postgresql+asyncpg://...) como psycopg2 (postgresql://...) — se normaliza
internamente.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

from app.core.config import get_settings
from app.models.persistencia import (
    EmailProcesado,
    EstadoEmail,
    MensajeSaliente,
    TipoMensajeSaliente,
)
from app.services.ingesta_planilla import (
    EstadoTramitePlanificado,
    PlanillaDia,
    TramitePlanificado,
    _normalizar_bastidor,
    _normalizar_matricula,
)

logger = logging.getLogger(__name__)


def _dsn() -> str:
    """Normaliza DATABASE_URL a formato psycopg2."""
    url = get_settings().database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)


class RepositorioPostgres:
    """Implementación PostgreSQL de RepositorioPipeline."""

    # ------------------------------------------------------------------ #
    # emails_procesados                                                    #
    # ------------------------------------------------------------------ #

    def guardar_email_procesado(self, ep: EmailProcesado) -> None:
        sql = """
            INSERT INTO emails_procesados
                (message_id, remitente, asunto, fecha_recibido, num_adjuntos, estado, error_detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO UPDATE
                SET estado = EXCLUDED.estado,
                    error_detalle = EXCLUDED.error_detalle
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    ep.message_id,
                    ep.remitente,
                    ep.asunto,
                    ep.fecha_recibido,
                    ep.num_adjuntos,
                    ep.estado.value,
                    ep.error_detalle or "",
                ))
            conn.commit()

    def mensaje_ids_procesados(self) -> set[str]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id FROM emails_procesados")
                rows = cur.fetchall()
        return {r["message_id"] for r in rows}

    def email_ya_procesado(self, message_id: str) -> bool:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM emails_procesados WHERE message_id = %s",
                    (message_id,),
                )
                return cur.fetchone() is not None

    # ------------------------------------------------------------------ #
    # mensajes_salientes                                                   #
    # ------------------------------------------------------------------ #

    def guardar_mensaje_saliente(self, ms: MensajeSaliente) -> None:
        sql = """
            INSERT INTO mensajes_salientes
                (tramite_id, destinatario, tipo, asunto, cuerpo, preparado_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    ms.tramite_id,
                    ms.destinatario,
                    ms.tipo.value,
                    ms.asunto,
                    ms.cuerpo,
                    ms.preparado_at,
                ))
            conn.commit()

    def marcar_mensaje_enviado(self, tramite_id: str, tipo: TipoMensajeSaliente) -> None:
        sql = """
            UPDATE mensajes_salientes
               SET enviado_at = NOW()
             WHERE tramite_id = %s AND tipo = %s AND enviado_at IS NULL
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tramite_id, tipo.value))
            conn.commit()

    def obtener_mensajes_pendientes(self, tipo: TipoMensajeSaliente) -> list[MensajeSaliente]:
        sql = """
            SELECT tramite_id, destinatario, tipo, asunto, cuerpo, preparado_at
              FROM mensajes_salientes
             WHERE tipo = %s AND enviado_at IS NULL
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tipo.value,))
                rows = cur.fetchall()
        return [
            MensajeSaliente(
                tramite_id=r["tramite_id"],
                destinatario=r["destinatario"],
                tipo=TipoMensajeSaliente(r["tipo"]),
                asunto=r["asunto"],
                cuerpo=r["cuerpo"],
                preparado_at=r["preparado_at"],
                enviado=False,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Métodos requeridos por RepositorioPipeline (Protocol)               #
    # ------------------------------------------------------------------ #

    def mensajes_pendientes_de_aviso2(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        s = get_settings()
        umbral = ahora - timedelta(minutes=s.escalado_aviso2_min)
        sql = """
            SELECT tramite_id, destinatario, preparado_at
              FROM mensajes_salientes
             WHERE tipo = %s AND enviado_at IS NULL AND preparado_at <= %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (TipoMensajeSaliente.AVISO_1.value, umbral))
                rows = cur.fetchall()
        return [(r["tramite_id"], r["destinatario"], r["preparado_at"]) for r in rows]

    def mensajes_pendientes_de_escalado(
        self, ahora: datetime
    ) -> list[tuple[str, str, datetime]]:
        s = get_settings()
        umbral = ahora - timedelta(minutes=s.escalado_admin_min)
        sql = """
            SELECT tramite_id, destinatario, preparado_at
              FROM mensajes_salientes
             WHERE tipo = %s AND enviado_at IS NULL AND preparado_at <= %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (TipoMensajeSaliente.AVISO_2.value, umbral))
                rows = cur.fetchall()
        return [(r["tramite_id"], r["destinatario"], r["preparado_at"]) for r in rows]

    # ------------------------------------------------------------------ #
    # Trámites (para control.py en modo BD real)                          #
    # ------------------------------------------------------------------ #

    def listar_tramites(
        self,
        estado: str | None = None,
        gestoria: str | None = None,
        tipo: str | None = None,
    ) -> list[dict]:
        conditions = []
        params: list = []
        if estado:
            conditions.append("t.estado = %s")
            params.append(estado.upper())
        if gestoria:
            conditions.append("g.nombre ILIKE %s")
            params.append(f"%{gestoria}%")
        if tipo:
            conditions.append("t.tipo = %s")
            params.append(tipo.upper())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT t.id, t.tipo, t.matricula, t.bastidor,
                   g.nombre AS gestoria, g.email AS gestoria_email,
                   t.estado, t.fecha_entrada, t.num_comprobante_dgt,
                   COUNT(d.id) AS num_docs
              FROM tramites t
              JOIN gestorias g ON g.id = t.gestoria_id
         LEFT JOIN documentos d ON d.tramite_id = t.id
             {where}
          GROUP BY t.id, g.nombre, g.email
          ORDER BY t.fecha_entrada DESC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def obtener_tramite(self, tramite_id: str) -> dict | None:
        sql = """
            SELECT t.id, t.tipo, t.matricula, t.bastidor,
                   g.nombre AS gestoria, g.email AS gestoria_email,
                   t.estado, t.fecha_entrada, t.num_comprobante_dgt
              FROM tramites t
              JOIN gestorias g ON g.id = t.gestoria_id
             WHERE t.id = %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tramite_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def documentos_de_tramite(self, tramite_id: str) -> list[dict]:
        sql = """
            SELECT d.id, d.nombre_original AS nombre,
                   d.tipo_detectado, dt.validez, d.nivel_confianza AS confianza
              FROM documentos d
              JOIN documento_tramite dt ON dt.documento_id = d.id
             WHERE dt.tramite_id = %s
          ORDER BY d.fecha_recibido DESC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tramite_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def mensajes_de_tramite(self, tramite_id: str) -> list[dict]:
        sql = """
            SELECT tipo, asunto, cuerpo, preparado_at, enviado_at, respondido_at
              FROM mensajes_salientes
             WHERE tramite_id = %s
          ORDER BY preparado_at DESC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tramite_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # planilla_dia / tramite_planificado                                  #
    # ------------------------------------------------------------------ #

    def guardar_planilla_dia(self, planilla: PlanillaDia) -> str:
        """Guarda la planilla y devuelve su id UUID."""
        sql = """
            INSERT INTO planilla_dia (fecha, tipo, fuente)
            VALUES (%s, %s, %s)
            ON CONFLICT (fecha, tipo) DO UPDATE
                SET fuente = EXCLUDED.fuente
            RETURNING id
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    planilla.fecha,
                    planilla.tipo.value,
                    planilla.fuente,
                ))
                planilla_id = cur.fetchone()["id"]
                conn.commit()
        return str(planilla_id)

    def guardar_tramite_planificado(self, tp: TramitePlanificado, planilla_id: str) -> str:
        sql = """
            INSERT INTO tramite_planificado
                (planilla_id, bastidor, matricula, nif_adquirente,
                 num_expediente, nombre_titular, tipo_tramite, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    planilla_id,
                    tp.bastidor or None,
                    tp.matricula or None,
                    tp.nif_adquirente or None,
                    tp.num_expediente or None,
                    tp.nombre_titular or None,
                    tp.tipo_tramite,
                    tp.estado.value,
                ))
                row_id = cur.fetchone()["id"]
                conn.commit()
        return str(row_id)

    def buscar_tramite_planificado_por_bastidor(self, bastidor: str) -> list[TramitePlanificado]:
        b = _normalizar_bastidor(bastidor)
        sql = """
            SELECT bastidor, matricula, nif_adquirente, num_expediente,
                   nombre_titular, tipo_tramite, estado, tramite_id
              FROM tramite_planificado
             WHERE bastidor = %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (b,))
                rows = cur.fetchall()
        return [_row_a_tramite_planificado(r) for r in rows]

    def buscar_tramite_planificado_por_matricula(self, matricula: str) -> list[TramitePlanificado]:
        m = _normalizar_matricula(matricula)
        sql = """
            SELECT bastidor, matricula, nif_adquirente, num_expediente,
                   nombre_titular, tipo_tramite, estado, tramite_id
              FROM tramite_planificado
             WHERE matricula = %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (m,))
                rows = cur.fetchall()
        return [_row_a_tramite_planificado(r) for r in rows]

    def listar_tramites_sin_match_hoy(self) -> list[dict]:
        """Emails registrados hoy sin match en planilla (para auditoría)."""
        sql = """
            SELECT email_message_id, confianza, metodo, creado_at
              FROM cruce_email_planilla
             WHERE metodo = 'sin_match'
               AND creado_at::date = CURRENT_DATE
          ORDER BY creado_at DESC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def guardar_cruce_resultado(
        self,
        email_message_id: str,
        tramite_planificado_id: str | None,
        confianza: str,
        metodo: str,
    ) -> None:
        sql = """
            INSERT INTO cruce_email_planilla
                (email_message_id, tramite_planificado_id, confianza, metodo)
            VALUES (%s, %s, %s, %s)
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (email_message_id, tramite_planificado_id, confianza, metodo))
            conn.commit()


def _row_a_tramite_planificado(r: dict) -> TramitePlanificado:
    return TramitePlanificado(
        bastidor=r.get("bastidor") or "",
        matricula=r.get("matricula") or "",
        nif_adquirente=r.get("nif_adquirente") or "",
        num_expediente=r.get("num_expediente") or "",
        nombre_titular=r.get("nombre_titular") or "",
        tipo_tramite=r.get("tipo_tramite") or "",
        estado=EstadoTramitePlanificado(r.get("estado", "sin_documentacion")),
        tramite_id=str(r["tramite_id"]) if r.get("tramite_id") else None,
    )
