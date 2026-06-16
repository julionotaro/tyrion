-- ============================================================
-- TYRION — Migración 002: tablas para ingesta de email y pipeline
-- ============================================================

-- Estado de procesamiento de un email entrante
CREATE TYPE estado_email AS ENUM (
    'RECIBIDO',    -- llegó, sin procesar
    'PROCESADO',   -- pipeline completó sin errores
    'ERROR'        -- pipeline falló (ver error_detalle)
);

-- Tipo de mensaje saliente (aviso a gestoría o escalado al admin)
CREATE TYPE tipo_mensaje_saliente AS ENUM (
    'aviso_1',    -- T+0   primer aviso automático a gestoría
    'aviso_2',    -- T+30  segundo aviso automático a gestoría
    'escalado'    -- T+60  escalado al administrativo (último recurso)
);

-- EMAILS PROCESADOS: deduplicación por Message-ID
-- Garantiza idempotencia: un reenvío o fallo de marcado IMAP no reinyecta el email.
CREATE TABLE emails_procesados (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id      TEXT NOT NULL UNIQUE,          -- RFC 2822 Message-ID
    remitente       VARCHAR(300),
    asunto          VARCHAR(500),
    fecha_recibido  TIMESTAMPTZ NOT NULL DEFAULT now(),
    num_adjuntos    INTEGER NOT NULL DEFAULT 0,
    estado          estado_email NOT NULL DEFAULT 'RECIBIDO',
    error_detalle   TEXT DEFAULT ''
);

CREATE INDEX idx_emails_message_id ON emails_procesados(message_id);
CREATE INDEX idx_emails_estado     ON emails_procesados(estado);

COMMENT ON TABLE emails_procesados IS
    'Registro de emails ya vistos. La clave de deduplicación es message_id (Message-ID RFC822).';

-- MENSAJES SALIENTES: avisos a gestoría y escalados al admin
-- Principio 4: PREPARADO ≠ ENVIADO. enviado_at NULL = mensaje preparado pero no enviado todavía.
CREATE TABLE mensajes_salientes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tramite_id      UUID REFERENCES tramites(id) ON DELETE CASCADE,
    destinatario    VARCHAR(300) NOT NULL,
    tipo            tipo_mensaje_saliente NOT NULL,
    asunto          VARCHAR(500),
    cuerpo          TEXT NOT NULL,
    preparado_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_at      TIMESTAMPTZ,                   -- NULL = PREPARADO (aún no enviado)
    respondido_at   TIMESTAMPTZ
);

CREATE INDEX idx_msgsalientes_tramite      ON mensajes_salientes(tramite_id);
CREATE INDEX idx_msgsalientes_tipo         ON mensajes_salientes(tipo);
CREATE INDEX idx_msgsalientes_no_enviados  ON mensajes_salientes(preparado_at)
    WHERE enviado_at IS NULL;

COMMENT ON TABLE mensajes_salientes IS
    'Avisos a gestoría (aviso_1/aviso_2) y escalados al admin. '
    'enviado_at NULL = PREPARADO. La integración SMTP marca enviado_at al enviar.';
COMMENT ON COLUMN mensajes_salientes.tipo IS
    'aviso_1=T+0 (gestoría); aviso_2=T+30 (gestoría); escalado=T+60 (admin, último recurso).';
