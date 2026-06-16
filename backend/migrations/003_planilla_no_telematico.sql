-- ============================================================
-- TYRION — Migración 003: Planilla del día + campo no_telematico
-- Sesión 7: Ingesta de planilla + cruce email↔planilla
--
-- El flujo real arranca en la planilla, no en el email (flujo-operativo §2).
-- La planilla es el universo de trabajo cerrado del día: define qué trámites
-- deben resolverse. El email completa la fila; no genera trámites huérfanos.
-- ============================================================

-- ---------- TIPOS ENUM ----------

CREATE TYPE tipo_planilla AS ENUM (
    'TRANSMISIONES',   -- Relación de Transmisiones (transferencias)
    'MATRICULAS'       -- Relación de Matrículas (matriculaciones)
);

CREATE TYPE fuente_planilla AS ENUM (
    'tempus',   -- exportada de Tempus / Gestión Tráfico
    'manual'    -- cargada manualmente (CSV subido por el administrativo)
);

CREATE TYPE estado_tramite_planificado AS ENUM (
    'sin_documentacion',   -- en planilla pero sin email recibido aún
    'con_documentacion',   -- email recibido y cruzado con la fila
    'validado',            -- cotejo OK, listo para presentar a DGT
    'escalado'             -- escalado al administrativo (último recurso)
);

-- ---------- TABLA PLANILLA_DIA ----------
-- Una por tipo por día: TRANSMISIONES y MATRICULAS son planillas separadas.

CREATE TABLE planilla_dia (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fecha       DATE NOT NULL,
    tipo        tipo_planilla NOT NULL,
    fuente      fuente_planilla NOT NULL DEFAULT 'tempus',
    creado_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fecha, tipo)   -- una planilla de cada tipo por día
);

-- ---------- TABLA TRAMITE_PLANIFICADO ----------
-- Cada fila de la planilla exportada de Tempus.

CREATE TABLE tramite_planificado (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    planilla_id       UUID NOT NULL REFERENCES planilla_dia(id) ON DELETE CASCADE,

    -- Campos de identificación (clave de cruce con emails)
    bastidor          VARCHAR(17),          -- VIN normalizado (mayúsculas, sin espacios)
    matricula         VARCHAR(10),
    nif_adquirente    VARCHAR(20),
    num_expediente    VARCHAR(50),
    nombre_titular    VARCHAR(200),

    tipo_tramite      VARCHAR(50) NOT NULL, -- TRANSFERENCIA | MATRICULACION | BAJA…
    estado            estado_tramite_planificado NOT NULL DEFAULT 'sin_documentacion',

    -- Vínculo con el trámite real (NULL hasta que se cruza y se crea el trámite)
    tramite_id        UUID REFERENCES tramites(id) ON DELETE SET NULL,

    creado_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice primario de búsqueda: bastidor (clave de cruce principal)
CREATE INDEX idx_tramite_planificado_bastidor
    ON tramite_planificado (bastidor)
    WHERE bastidor IS NOT NULL;

-- Índice secundario: matrícula
CREATE INDEX idx_tramite_planificado_matricula
    ON tramite_planificado (matricula)
    WHERE matricula IS NOT NULL;

-- Índice para consultas por planilla
CREATE INDEX idx_tramite_planificado_planilla
    ON tramite_planificado (planilla_id);

-- ---------- COLUMNA no_telematico EN tramites ----------
-- Históricos (ART.11 RD982/2024) y ciertos agrícolas van a Jefatura (no telemático).
-- flag no_telematico=True → estado "pendiente_jefatura", nunca escalar al admin.

ALTER TABLE tramites
    ADD COLUMN IF NOT EXISTS no_telematico BOOLEAN NOT NULL DEFAULT false;

-- ---------- TABLA cruce_email_planilla (auditoría) ----------
-- Registra cada intento de cruce email↔planilla para trazabilidad.

CREATE TABLE cruce_email_planilla (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_message_id      VARCHAR(500) NOT NULL,
    tramite_planificado_id UUID REFERENCES tramite_planificado(id) ON DELETE SET NULL,
    confianza             VARCHAR(10) NOT NULL,  -- ALTA | MEDIA | BAJA | NINGUNA
    metodo                VARCHAR(30) NOT NULL,  -- bastidor_exacto | bastidor_4dig | matricula | nif | sin_match
    creado_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cruce_email_message_id
    ON cruce_email_planilla (email_message_id);
