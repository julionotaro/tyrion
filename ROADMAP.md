# ROADMAP — Tyrion

Capa de inteligencia documental para el Colegio de Gestores (cliente Alfa-Pyme).
Gestiona trámites de vehículos ante DGT para 70 gestorías (~200 trámites/día).

## Módulos completados

### Sesión 1 — Fundamento (fecha original)
- ✅ Schema PostgreSQL completo (`backend/migrations/001_initial_schema.sql`)
- ✅ Clasificador documental con Claude API (`backend/app/services/clasificador.py`)
- ✅ Catálogo del dominio DGT (`backend/app/services/catalogo_documental.py`)
- ✅ 15 tests — `backend/tests/test_clasificador.py`

### Sesión 2 — Motor de cotejo (15/06/2026)
- ✅ Motor de cotejo documental (`backend/app/services/motor_cotejo.py`)
  - Decide VALIDO / EVIDENCIA_COMPATIBLE / RECHAZADO / NO_APLICA por vínculo
  - `evaluar_checklist()` + `CHECKLIST_POR_TRAMITE` por tipo de trámite
  - `preparar_mensaje_gestoria()` — Tyrion pide a gestoría primero
  - Principio de escalado: admin solo como último recurso
- ✅ 18 tests nuevos — `backend/tests/test_motor_cotejo.py`
- ✅ Suite acumulada: 33 tests pasando

### Sesión 3 — Ingesta de email + pipeline automático (15/06/2026)
- ✅ Ingesta IMAP genérica (`backend/app/services/ingesta_email.py`)
  - Polling de bandeja, deduplicación por Message-ID
  - Extracción de adjuntos PDF e imagen
  - Fuente abstraída (IMAP real / en memoria para tests)
- ✅ Pipeline automático (`backend/app/services/pipeline.py`)
  - Adjunto → clasificador → motor de cotejo → avisos automáticos
  - T+0min aviso_1 a gestoría (automático al detectar faltante)
  - T+30min aviso_2 a gestoría (timer vía `ejecutar_timers()`)
  - T+60min escalado al administrativo (ÚLTIMO recurso, nunca el primero)
  - `RepositorioEnMemoria` para tests sin BD
- ✅ Modelos de persistencia (`backend/app/models/persistencia.py`)
  - `EmailProcesado` — deduplicación
  - `MensajeSaliente` — ciclo de vida de avisos
- ✅ Migración SQL (`backend/migrations/002_ingesta_pipeline.sql`)
  - Tablas `emails_procesados` y `mensajes_salientes`
- ✅ Config ampliada con parámetros IMAP/SMTP y timers de escalado
- ✅ 20 tests nuevos — `backend/tests/test_ingesta_email.py` + `test_pipeline.py`
- ✅ Suite acumulada: **53 tests pasando**

### Sesión 4a — Pantalla Control (15/06/2026)
- ✅ API REST FastAPI (`backend/app/api/control.py`)
  - `GET /api/tramites` con filtros estado/gestoría/tipo
  - `GET /api/tramites/{id}` detalle completo
  - `GET /api/stats` conteos para los 6 cards
  - `POST /api/tramites/{id}/escalar` escalado manual
- ✅ Frontend vanilla JS (`backend/static/index.html`)
  - 6 cards de macro-estado clicables (filtran la tabla)
  - Tabla con búsqueda texto, filtro tipo, badge de alerta
  - Panel lateral: documentos con validez, historial, avisos pendientes
  - Botón "Escalar" visible solo en pendiente_gestoria
  - Polling automático cada 30 segundos
  - Sin dependencias externas
- ✅ Datos de prueba (`backend/app/api/datos_prueba.py`) — 8 trámites, 6 estados
- ✅ `backend/app/main.py` — FastAPI app con router y static files
- ✅ 19 tests nuevos — `backend/tests/test_control_api.py`
- ✅ Suite acumulada: **72 tests pasando**

### Sesión 4b — Docker + Split-view documental (15/06/2026)
- ✅ Infraestructura Docker (`docker-compose.yml`, `backend/Dockerfile`, `backend/entrypoint.sh`)
  - Servicio `db` (PostgreSQL 15), `api` (FastAPI), `worker` (timers pipeline)
  - `entrypoint.sh`: espera pg, corre migraciones, arranca uvicorn o worker
  - `make up/down/logs/test/shell/migrate/reset`
  - `.env.example` completo
- ✅ Split-view documental en frontend (`backend/static/index.html`)
  - Panel derecho: campos extraídos con ✓ verde / ⚠ naranja / ✗ rojo
  - Panel izquierdo: iframe PDF (placeholder hasta sesión 6)
  - Banner de validez coloreado por estado del documento
  - Enlace "Ver" solo para documentos con extracción disponible
- ✅ API documentos (`backend/app/api/documentos.py`)
  - `GET /api/tramites/{id}/documentos` → lista con validez
  - `GET /api/documentos/{doc_id}/extraccion` → campos extraídos + cotejo
  - `GET /api/documentos/{doc_id}/archivo` → 503 placeholder (TODO sesión 6)
- ✅ Datos de prueba extendidos — 8 documentos con campos_extraidos en `datos_prueba.py`
  - doc-005: CTI en vez de permiso → EVIDENCIA_COMPATIBLE (caso confusión real)
  - doc-007: hoja de caja → RECHAZADO (documento irrelevante)
- ✅ 11 tests nuevos — `backend/tests/test_documentos_api.py`
- ✅ Suite acumulada: **77 tests pasando** (6 de pipeline con incompatibilidad de entorno httpx/anthropic, pre-existentes)

## Pendiente (próximas sesiones)

### Sesión 4 — Pendiente confirmación en sesión con cliente
- 🔜 Tiempos reales de SLA por tipo de trámite
  (ahora: T+30/T+60 fijos en config; pueden variar por TRANSFERENCIA vs BAJA)
- 🔜 % de documentos que llegan mal (métrica real para ajustar umbrales)
- 🔜 Canal oficial con gestorías: ¿Tempus, email o teléfono? (TODO en pipeline.py)
- 🔜 Integración SMTP real (ahora los mensajes quedan en PREPARADO)
- 🔜 Pantalla Control (6 macro-estados) — FastAPI + frontend mínimo
- 🔜 Cruce hoja de caja / albarán SAGE

### Sesión 5 — Fix httpx/anthropic + Repositorio PostgreSQL (15/06/2026)
- ✅ Fix incompatibilidad httpx 0.28 / anthropic 0.39 (`anthropic` → `0.109.1`)
  - 6 tests de `test_pipeline.py` que fallaban por `proxies` kwarg eliminado en httpx 0.28
  - Suite completa: **83 tests pasando, 0 fallos**
- ✅ Repositorio PostgreSQL (`backend/app/repositories/repositorio_postgres.py`)
  - Implementa la misma interfaz que `RepositorioEnMemoria` (intercambiable sin cambiar Pipeline)
  - `guardar_email_procesado()` con `ON CONFLICT DO UPDATE` (idempotente)
  - `mensajes_pendientes_de_aviso2/escalado()` con umbral de tiempo desde settings
  - `listar_tramites()`, `obtener_tramite()`, `documentos_de_tramite()`, `mensajes_de_tramite()` para la Pantalla Control
  - Transacciones explícitas con `conn.commit()` + rollback automático en error
- ✅ `pipeline.py` — nueva función `crear_repositorio()` que selecciona Postgres o EnMemoria según `USE_DATOS_PRUEBA`
- ✅ `control.py` — endpoints leen de PostgreSQL cuando `USE_DATOS_PRUEBA=false`
  - Contrato de respuesta idéntico: sin cambios en frontend
- ✅ `pytest.ini` — mark `integration` registrado
- ✅ `test_repositorio_postgres.py` — 5 tests marcados `@pytest.mark.integration`
  - Se saltan automáticamente sin BD disponible
  - Correr con: `pytest -m integration` cuando hay Docker up
- ⏭ TAREA 3 (verificación Docker end-to-end): Docker daemon no disponible en entorno cloud
  - Ejecutar `make up && curl http://localhost:8000` en local para verificar

### Sesión 6 — Refactor motor de cotejo a árbol condicional (15/06/2026)
- ✅ `docs/matriz-documental-tramites.md` — referencia canónica commiteada (§1-§11)
- ✅ `catalogo_documental.py` ampliado:
  - `FamiliaTramite`: TRANSFERENCIA, MATRICULACION, BAJA, CAMBIO_DOMICILIO,
    DUPLICADO_CIRCULACION, DUPLICADO_FICHA, CONDUCTORES, PLACAS_VERDES, PLACAS_ROJAS
  - `SubtipoTramite`: compraventa_particular, compra_empresa, herencia, nuevo, usado
  - `OrigenVehiculo`: espana, ue, fuera_ue, subasta
  - `TipoVehiculo`: turismo, remolque, agricola, historico
  - `NaturalezaPartes`: particular, empresa_adquirente, empresa_transmitente
  - 16 nuevos `TipoDocumento` (solicitud_matriculacion, ivtm, modelo_650, etc.)
- ✅ `motor_cotejo.py` refactorizado:
  - `resolver_checklist(familia, subtipo, origen, tipo_vehiculo, naturaleza_partes)` — árbol puro
  - `ChecklistResuelto`: requisitos + flags (`no_telematico`, `requiere_revision_manual`)
  - Reglas §5: remolque sin impuesto_matriculacion, agrícola+cartilla, histórico+flag,
    nuevo/usado+doc.extranjera, herencia+650+herederos, empresa+poder+cif
  - 9 familias de trámite cubiertas (no solo 3)
  - `MotorCotejo` y tests existentes intactos
- ✅ `cruces.py` (NUEVO) — validaciones multi-documento con clave primaria = bastidor:
  - `cruce_transferencia()`: bastidor(permiso↔CTI↔620), CET con tolerancia 5%, NIF transmitente
  - `cruce_herencia()`: causante(650↔defunción↔CTI), bastidor en Anexo 650
  - `cruce_matriculacion()`: bastidor en 4 documentos, potencia kW ficha↔IVTM
  - `ResultadoCruce` con `severidad_maxima`, `ok`, `requiere_revision_manual`
  - Severidades: OK / EVIDENCIA (gestoría) / RECHAZADO (admin, último recurso)
- ✅ 40 tests nuevos — `test_resolver_checklist.py` (20) + `test_cruces.py` (20)
- ✅ Suite acumulada: **123 pasando, 5 skipped, 0 fallos**

**TODO documentado (sesión siguiente):**
- Ingesta de planilla (Relación Transmisiones/Matrículas)
- Cruce email ↔ planilla (trámites del día vs. correos recibidos)
- Campo `no_telematico` en tabla `tramites` + migración SQL
- Integración `resolver_checklist()` con tabla `requisitos_tramite` en BD

## ESTADO SESIÓN — 15/06/2026 (última)

### Completado en esta sesión (docs)
- `docs/flujo-operativo-estandarizado.md` commiteado — 5 fases del proceso real, mapa a módulos Tyrion, tabla diferencias con modelo previo, pendientes sesión 2
- `docs/instructivo-operativo.md` commiteado — checklists por familia, cruces requeridos, tabla identificación de personas, descripción automáticas de Tyrion, preguntas sesión 2

### Próxima acción concreta
- **Sesión 7**: Ingesta de planilla + cruce email↔planilla + campo `no_telematico` en BD

### Decisiones tomadas
- `docs/` es la referencia canónica de proceso (junto con `matriz-documental-tramites.md` ya existente)
