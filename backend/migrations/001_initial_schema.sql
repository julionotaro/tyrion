-- ============================================================
-- TYRION — Schema PostgreSQL v1.0
-- Proyecto: Alfa-Pyme / Colegio de Gestores
-- Capa de inteligencia documental sobre gestión de trámites DGT
--
-- Principios de diseño (del análisis de entrevista sesión 1):
--   1. La validez de un documento vive en el VÍNCULO documento-trámite,
--      NUNCA en el documento. Un mismo documento puede ser válido en un
--      trámite y evidencia compatible en otro.
--   2. Evidencia compatible ≠ documento válido (regla de oro).
--   3. Estados de trámite confirmados (4): PENDIENTE, EN_REVISION,
--      PRESENTADO, FINALIZADO.
--   4. Mensaje preparado ≠ mensaje enviado.
--   5. Tyrion prepara; el humano presenta físicamente a DGT.
-- ============================================================

-- ---------- EXTENSIONES ----------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- búsqueda por similitud (matrículas, nombres)

-- ---------- TIPOS ENUM ----------

-- Estados del trámite (confirmados en sesión 1, definitivos)
CREATE TYPE estado_tramite AS ENUM (
    'PENDIENTE',     -- documentación incompleta, esperando a la gestoría
    'EN_REVISION',   -- documentación recibida, siendo cotejada por el Colegio
    'PRESENTADO',    -- expediente llevado físicamente a DGT
    'FINALIZADO'     -- permisos impresos, trámite cerrado
);

-- Tipo de trámite (en v1 todos comparten pipeline)
CREATE TYPE tipo_tramite AS ENUM (
    'TRANSFERENCIA',
    'MATRICULACION',
    'BAJA'
);

-- Canal de entrada de un documento (WhatsApp/Telegram NO se usan)
CREATE TYPE canal_documento AS ENUM (
    'EMAIL',
    'PAPEL_FISICO'
);

-- Estado de la máquina de estados PROPIA del documento
-- (independiente del trámite)
CREATE TYPE estado_documento AS ENUM (
    'RECIBIDO',           -- llegó, sin clasificar
    'CLASIFICADO',        -- Tyrion detectó su tipo con confianza
    'SUSTITUIDO'          -- una versión más nueva lo reemplazó
);

-- Nivel de confianza de la clasificación de Tyrion
CREATE TYPE nivel_confianza AS ENUM (
    'ALTA',     -- >= 0.85
    'MEDIA',    -- 0.60 - 0.84
    'BAJA'      -- < 0.60 -> marca para validación humana
);

-- Validez de un documento RESPECTO A UN TRÁMITE (vive en el vínculo)
CREATE TYPE validez_vinculo AS ENUM (
    'VALIDO',                 -- desbloquea ESE requisito de ESE trámite
    'EVIDENCIA_COMPATIBLE',   -- relacionado pero NO desbloquea (regla de oro)
    'RECHAZADO',              -- no sirve / incorrecto
    'NO_APLICA'               -- no corresponde a este trámite
);

-- Estado del ciclo de vida de un mensaje a la gestoría
CREATE TYPE estado_mensaje AS ENUM (
    'PREPARADO',    -- Tyrion lo redactó, aún no salió
    'ENVIADO',      -- salió por el canal
    'RESPONDIDO'    -- la gestoría contestó
);

-- ---------- TABLAS NÚCLEO ----------

-- GESTORÍAS: las 70 entidades cliente del Colegio
CREATE TABLE gestorias (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre          VARCHAR(200) NOT NULL,
    -- identidades autorizadas: ningún documento se asocia sin remitente reconocido
    emails          TEXT[] NOT NULL DEFAULT '{}',
    telefonos       TEXT[] NOT NULL DEFAULT '{}',
    activa          BOOLEAN NOT NULL DEFAULT TRUE,
    creada_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizada_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN gestorias.emails IS 'Emails autorizados. Un remitente fuera de esta lista queda en cuarentena de identidad.';

-- TRÁMITES: la unidad operativa
CREATE TABLE tramites (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo                 tipo_tramite NOT NULL,
    gestoria_id          UUID NOT NULL REFERENCES gestorias(id),
    -- identificadores del caso
    matricula            VARCHAR(20),
    bastidor             VARCHAR(30),
    -- estado en Tempus (PENDIENTE_CONFIRMACION en specs originales; confirmados en sesión 1)
    estado               estado_tramite NOT NULL DEFAULT 'PENDIENTE',
    -- comprobante físico que DGT entrega al presentar (confirmado en sesión 2)
    num_comprobante_dgt  VARCHAR(50),
    -- responsable actual: NULL = Tyrion; UUID = administrativo concreto (escalado)
    responsable_admin_id UUID,
    -- SLA: todos los trámites cierran en el día
    fecha_entrada        TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_presentado     TIMESTAMPTZ,
    fecha_finalizado     TIMESTAMPTZ,
    creado_en            TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- al menos uno de los identificadores del caso debe existir
    CONSTRAINT chk_identificador CHECK (matricula IS NOT NULL OR bastidor IS NOT NULL)
);

CREATE INDEX idx_tramites_estado       ON tramites(estado);
CREATE INDEX idx_tramites_gestoria     ON tramites(gestoria_id);
CREATE INDEX idx_tramites_matricula    ON tramites USING gin(matricula gin_trgm_ops);
CREATE INDEX idx_tramites_fecha_entrada ON tramites(fecha_entrada);

COMMENT ON COLUMN tramites.responsable_admin_id IS 'NULL = Tyrion gestiona. Un UUID indica escalado a un administrativo concreto.';
COMMENT ON COLUMN tramites.num_comprobante_dgt IS 'Comprobante físico que DGT entrega al recibir el expediente (confirmado sesión 2).';

-- DOCUMENTOS: máquina de estados propia, independiente del trámite
CREATE TABLE documentos (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- archivo
    nombre_archivo      VARCHAR(500) NOT NULL,
    ruta_almacen        VARCHAR(1000) NOT NULL,
    hash_contenido      VARCHAR(64) NOT NULL,        -- sha256 para detectar duplicados
    canal               canal_documento NOT NULL,
    -- remitente: se matchea contra identidades de gestoría
    remitente_raw       VARCHAR(300),                -- email/teléfono crudo de origen
    gestoria_id         UUID REFERENCES gestorias(id), -- NULL = en cuarentena de identidad
    -- clasificación de Tyrion (las 4 capas: este es el "detectado")
    tipo_detectado      VARCHAR(100),                -- p.ej. 'permiso_circulacion', 'modelo_620'
    confianza_score     NUMERIC(4,3),                -- 0.000 - 1.000
    confianza_nivel     nivel_confianza,
    -- estado de la máquina propia del documento
    estado              estado_documento NOT NULL DEFAULT 'RECIBIDO',
    -- versionado: un reenvío corregido SUSTITUYE y conserva el anterior
    version             INTEGER NOT NULL DEFAULT 1,
    sustituye_a         UUID REFERENCES documentos(id),
    -- ubicación física si es papel (para cadetería/devolución)
    ubicacion_fisica    VARCHAR(200),
    recibido_en         TIMESTAMPTZ NOT NULL DEFAULT now(),
    clasificado_en      TIMESTAMPTZ,
    UNIQUE (hash_contenido)
);

CREATE INDEX idx_documentos_gestoria   ON documentos(gestoria_id);
CREATE INDEX idx_documentos_tipo       ON documentos(tipo_detectado);
CREATE INDEX idx_documentos_estado     ON documentos(estado);
CREATE INDEX idx_documentos_cuarentena ON documentos(id) WHERE gestoria_id IS NULL;

COMMENT ON COLUMN documentos.gestoria_id IS 'NULL = documento en cuarentena de identidad (remitente no reconocido). Tyrion pregunta; si no resuelve, escala.';
COMMENT ON COLUMN documentos.tipo_detectado IS 'Capa 3 (detectado): lo que Tyrion interpreta. NO es lo mismo que documento válido (capa 4).';

-- VÍNCULO Documento ↔ Trámite (N:M) — AQUÍ vive la validez
-- Regla central: la validez NUNCA es propiedad del documento, sino de la relación.
CREATE TABLE documento_tramite (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id    UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    tramite_id      UUID NOT NULL REFERENCES tramites(id) ON DELETE CASCADE,
    -- qué requisito del checklist cubre (o intenta cubrir) este documento
    requisito       VARCHAR(100),                    -- p.ej. 'permiso_circulacion'
    -- la validez vive aquí, no en el documento
    validez         validez_vinculo NOT NULL DEFAULT 'NO_APLICA',
    -- motivo si es EVIDENCIA_COMPATIBLE o RECHAZADO (para el resumen de escalado)
    motivo          TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (documento_id, tramite_id, requisito)
);

CREATE INDEX idx_doctram_tramite   ON documento_tramite(tramite_id);
CREATE INDEX idx_doctram_documento ON documento_tramite(documento_id);
CREATE INDEX idx_doctram_validez   ON documento_tramite(validez);

COMMENT ON TABLE documento_tramite IS 'Relación N:M. La validez de un documento es propiedad de ESTE vínculo, no del documento. Un mismo documento puede ser VALIDO en un trámite y EVIDENCIA_COMPATIBLE en otro.';

-- CHECKLIST DE REQUISITOS por tipo de trámite
-- (catálogo de qué documentos exige cada tipo; base de datos viva, editable)
CREATE TABLE requisitos_tramite (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo            tipo_tramite NOT NULL,
    requisito       VARCHAR(100) NOT NULL,           -- 'permiso_circulacion', 'modelo_620', etc.
    descripcion     TEXT,
    obligatorio     BOOLEAN NOT NULL DEFAULT TRUE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (tipo, requisito)
);

COMMENT ON TABLE requisitos_tramite IS 'Checklist por tipo. La lista puede cambiar a mitad del trámite (ej: herencia exige certificado de defunción tras validar). Editable sin redeploy.';

-- MENSAJES a la gestoría (preparado ≠ enviado)
CREATE TABLE mensajes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tramite_id      UUID NOT NULL REFERENCES tramites(id) ON DELETE CASCADE,
    gestoria_id     UUID NOT NULL REFERENCES gestorias(id),
    canal           canal_documento NOT NULL DEFAULT 'EMAIL',
    asunto          VARCHAR(300),
    cuerpo          TEXT NOT NULL,
    estado          estado_mensaje NOT NULL DEFAULT 'PREPARADO',
    preparado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_en      TIMESTAMPTZ,
    respondido_en   TIMESTAMPTZ
);

CREATE INDEX idx_mensajes_tramite ON mensajes(tramite_id);
CREATE INDEX idx_mensajes_estado  ON mensajes(estado);

COMMENT ON COLUMN mensajes.estado IS 'PREPARADO = Tyrion lo redactó pero no salió. Si no hay integración de envío real, el sistema dice PREPARADO, nunca ENVIADO.';

-- ALBARANES: registro diario por gestoría para carga (manual) en SAGE
CREATE TABLE albaranes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gestoria_id     UUID NOT NULL REFERENCES gestorias(id),
    numero_serie    VARCHAR(50),                     -- número de serie del albarán
    fecha           DATE NOT NULL,
    gestor          VARCHAR(200),
    -- detalle: tipos de trámite por código, cantidades
    detalle         JSONB NOT NULL DEFAULT '{}',
    -- cruce contra Tempus: detectar desvíos (facturado no cerrado / cerrado no facturado)
    cruzado         BOOLEAN NOT NULL DEFAULT FALSE,
    cargado_sage    BOOLEAN NOT NULL DEFAULT FALSE,  -- carga manual confirmada por humano
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_albaranes_gestoria ON albaranes(gestoria_id);
CREATE INDEX idx_albaranes_fecha    ON albaranes(fecha);

COMMENT ON TABLE albaranes IS 'La gestoría envía la hoja de caja por email. Tyrion la procesa y prepara el albarán. La carga en SAGE es manual (humano confirma).';

-- AUDITORÍA: historial de transiciones de estado (trazabilidad regulada)
CREATE TABLE auditoria_eventos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entidad_tipo    VARCHAR(50) NOT NULL,            -- 'tramite', 'documento', 'mensaje'
    entidad_id      UUID NOT NULL,
    evento          VARCHAR(100) NOT NULL,           -- 'cambio_estado', 'escalado', 'clasificado'
    estado_anterior VARCHAR(50),
    estado_nuevo    VARCHAR(50),
    actor           VARCHAR(100) NOT NULL DEFAULT 'tyrion',  -- 'tyrion' o id de admin
    detalle         JSONB DEFAULT '{}',
    ocurrido_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_auditoria_entidad ON auditoria_eventos(entidad_tipo, entidad_id);
CREATE INDEX idx_auditoria_fecha   ON auditoria_eventos(ocurrido_en);

-- ---------- TRIGGER: actualizar actualizado_en ----------
CREATE OR REPLACE FUNCTION touch_actualizado_en()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tramites_touch
    BEFORE UPDATE ON tramites
    FOR EACH ROW EXECUTE FUNCTION touch_actualizado_en();

CREATE TRIGGER trg_gestorias_touch
    BEFORE UPDATE ON gestorias
    FOR EACH ROW EXECUTE FUNCTION touch_actualizado_en();
