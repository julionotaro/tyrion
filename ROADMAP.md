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

### Sesión 7 — Ingesta de planilla + cruce email↔planilla + BD (16/06/2026)
- ✅ Migración SQL 003 (`backend/migrations/003_planilla_no_telematico.sql`)
  - Tablas `planilla_dia`, `tramite_planificado`, `cruce_email_planilla`
  - Columna `no_telematico` en `tramites` + índices bastidor/matrícula
- ✅ `ingesta_planilla.py` (NUEVO) — parsers puros de CSV Tempus
  - `parse_relacion_transmisiones()` y `parse_relacion_matriculas()`
  - Normalización bastidor (uppercase, sin espacios/guiones) y matrícula
  - `PlanillaDia.buscar_por_bastidor()` / `buscar_por_matricula()`
- ✅ `cruce_planilla.py` (NUEVO) — cruce email↔planilla
  - Bastidor exacto → ALTA; últimos 4 dígitos → MEDIA; matrícula → MEDIA; NIF → BAJA
  - Emails sin match NO se bloquean, continúan flujo normal
  - Detección de ambigüedad (múltiples candidatos)
- ✅ `pipeline.py` ampliado
  - Cruce email↔planilla al inicio del procesamiento
  - `no_telematico=True` → pendiente_jefatura (early return antes de generar avisos)
  - `ResultadoPipeline.cruce_planilla` + `ResultadoPipeline.no_telematico`
- ✅ `repositorio_postgres.py` ampliado — guardar/buscar planilla y trámites planificados
- ✅ `control.py` — 3 endpoints nuevos + stats ampliado
  - `POST /api/planilla`, `GET /api/planilla/hoy`, `GET /api/planilla/sin-match`
  - `StatsResponse` con `total_planificados`, `sin_match`, `pendiente_jefatura`, `sin_documentacion`
- ✅ `datos_prueba.py` — `PLANILLA_DIA_PRUEBA` (9 trámites planificados + 1 email sin match)
- ✅ 46 tests nuevos (test_ingesta_planilla, test_cruce_planilla, test_pipeline_planilla)
- ✅ Suite acumulada: **169 pasando, 5 skipped, 0 fallos**

### Sesión 8 — PDFs reales + watcher Tempus + make demo (16/06/2026)
- ✅ `storage.py` (NUEVO) — almacenamiento local de archivos
  - `guardar_archivo(doc_id, bytes, nombre, mime)` → guarda en uploads_dir/{doc_id}/
  - `obtener_archivo(doc_id)` → (bytes, mime_type) | FileNotFoundError
- ✅ `documentos.py` — endpoint `/api/documentos/{doc_id}/archivo` operativo
  - Antes: 503 placeholder. Ahora: sirve el PDF real con `Response(content, media_type)`
  - 404 si el archivo no existe en disco
- ✅ `config.py` ampliado
  - `uploads_dir: str = "/tmp/tyrion_uploads"` (antes: /var/tyrion/uploads, sin watch_dir)
  - `watch_dir: str = "/tmp/tyrion_watch"` (nuevo)
- ✅ `migrations/004_storage.sql` — columnas `archivo_path` y `archivo_mime` en `documentos`
- ✅ `watcher_planilla.py` (NUEVO) — polling automático de CSVs Tempus
  - `procesar_archivo(ruta)` → parsea, mueve a procesados/, devuelve nº trámites
  - `run_watcher(intervalo, repo)` — tarea asyncio periódica para el worker
- ✅ `docker-compose.yml` corregido
  - Volúmenes `data/uploads:/tmp/tyrion_uploads` (api) y `data/watch:/tmp/tyrion_watch` (worker)
  - `DATABASE_URL` corregido a `postgresql+asyncpg://...` (era `postgresql://...`)
  - Env vars `UPLOADS_DIR` y `WATCH_DIR` en ambos servicios
- ✅ `tools/cargar_docs_prueba.py` — genera 8 PDFs mínimos para demo local
- ✅ `tools/datos_muestra/` — CSVs de muestra (8 transmisiones + 3 matrículas)
- ✅ `Makefile` — target `demo` (docker up → cargar docs → drop CSVs en watch_dir)
- ✅ `README.md` — sección "Demo en 1 comando"
- ✅ `backend/.env.example` — variables `WATCH_DIR` y `UPLOADS_DIR`
- ✅ 9 tests nuevos (test_storage × 4, test_watcher_planilla × 4, test_demo × 1)
- ✅ Suite acumulada: **178 pasando, 5 skipped, 0 fallos**

### Sesión 8b — Modo demo sin API key (16/06/2026)
- ✅ `clasificador.py` — `ClasificadorMock` integrado en `ClasificadorDocumental`
  - Sin `ANTHROPIC_API_KEY`: usa mock automáticamente (log: "Clasificador: modo mock")
  - Mock infiere tipo desde `tipo_declarado`; sin key nunca lanza error
- ✅ `backend/.env.example` — `ANTHROPIC_API_KEY=` vacío con comentario explicativo
- ✅ `README.md` — demo sin cuenta Anthropic documentada
- ✅ 3 tests nuevos (test_clasificador_usa_mock_sin_api_key, test_mock_*, ×3)
- ✅ Suite acumulada: **181 pasando, 5 skipped, 0 fallos**

### Sesión 9 — Tests de escenarios de negocio + fix de 4 bugs críticos (16/06/2026)
- ✅ Metodología test-rojo → fix → test-verde aplicada en todos los bugs
- ✅ **BUG 1 (Crítico)**: Escalado inmediato sin avisos previos — CORREGIDO
  - Eliminado bloque de escalado directo en `procesar_email()` (líneas 332-352)
  - `EstadoChecklist.debe_pedir_gestoria` ahora incluye rechazados (aviso_1 T+0)
  - Escalado solo ocurre via `ejecutar_timers()` tras aviso_1 + aviso_2 sin respuesta
- ✅ **BUG 2 (Alta)**: Estado no avanza a listo_dgt — CORREGIDO
  - `ResultadoPipeline.listo_dgt` property: True cuando checklist completo y no no_telematico
- ✅ **BUG 3 (Alta)**: CTI como EVIDENCIA en transferencia — CORREGIDO
  - `CHECKLIST_POR_TRAMITE[TRANSFERENCIA]`: `"cti"` reemplaza `"permiso_circulacion"`
  - `resolver_checklist()` TRANSFERENCIA actualizado igualmente
  - CTI es el documento PRINCIPAL de transferencia (Cambio Titularidad Individual)
- ✅ **BUG 4 (Baja)**: Badge alertas no filtraba tabla — CORREGIDO
  - `filtroAlertas()` añadido al badge con toggle activo/inactivo
  - `renderTabla()` filtra por `t.alerta` cuando `filtroAlertaActivo=true`
  - `limpiarFiltros()` resetea el filtro de alerta
- ✅ `test_escenarios_negocio.py` (NUEVO) — 12 tests end-to-end
  - Transferencia completa → listo_dgt; sin docs → aviso_1 (no escalado)
  - CTI es VALIDO en transferencia; herencia completa → listo_dgt
  - Rechazado → aviso_1 a gestoría (nunca escalado directo)
  - Escalado SOLO tras aviso_1 + aviso_2 sin respuesta (timer T+60)
  - Matriculación tipo A completa; remolque sin impuesto; histórico → jefatura
  - Badge alertas y avance automático a listo_dgt
- ✅ `test_api_estados.py` (NUEVO) — 7 tests API de estados y escalado
- ✅ Tests de regresión actualizados (test_motor_cotejo, test_resolver_checklist)
- ✅ Suite acumulada: **200 pasando, 5 skipped, 0 fallos**

### Sesión 10a — Rediseño visual Pantalla Control (16/06/2026)
- ✅ `backend/static/index.html` — rediseño visual completo (solo CSS/JS, sin tocar Python)
  - Fuente Inter (Google Fonts) + sistema de custom properties CSS (20 variables)
  - Paleta: `--navy` header, `--blue` activo, `--alert` rojo, `--success` verde, `--warn` ámbar
  - `<header>` (56px, fondo navy): logo + `#cards` barra de estados inline + badge alertas
  - `.card` como segmentos con separadores `::after` flecha → aspecto pipeline visual
  - `body` flex-column 100vh; `#main` flex:1 min-height:0 (scroll correcto sin viewport overflow)
  - `#panel-tabla` flex-column con `tabla-wrapper` scrollable independiente
  - `#panel-detalle` 380px fijo con border-left; `#panel-split` 560px cuando visible
  - `formatTiempo(mins)` — duración humana: "15m", "1h 30m", "2d 4h"
  - Tabla: columna tiempo con `formatTiempo()` + columna `N docs` en vez de contador plano
  - Todo el JS original preservado (mismos IDs, event listeners, funciones)
- ✅ Suite acumulada: **200 pasando, 5 skipped, 0 fallos** (sin cambios en tests)

### Sesión 11 — Carga manual + OpenAI productivo + indicador de salud (16/06/2026)

**Contexto real**: 60% de gestorías entrega documentación en papel; la carga manual es la vía estándar, no una excepción.

- ✅ `backend/app/api/carga.py` (NUEVO) — API de carga manual de documentos
  - `POST /api/carga/tramite` → crea trámite manual (tipo, subtipo, matrícula, bastidor, gestoría)
  - `POST /api/carga/tramite/{id}/documento` → sube archivo, dispara clasificación + cotejo, devuelve resultado por documento
  - `GET  /api/carga/tramite/{id}/resultado` → estado final del checklist completo
  - Almacenamiento en memoria de sesión (demo); en producción usará RepositorioPostgres
- ✅ `backend/static/carga.html` (NUEVO) — pantalla de carga manual
  - Formulario en 3 pasos: datos del trámite → subida de documentos → resultado del cotejo
  - Drag&drop o selector multi-archivo; cada documento muestra en vivo: tipo detectado, validez (✓/⚠/✗), confianza
  - Resultado con estado final: Listo para DGT / Pendiente gestoría + lista de faltantes
  - Diseño coherente con index.html (misma paleta Inter + CSS custom properties)
- ✅ `backend/static/index.html` (modificado) — botón "+ Cargar trámite" en header + indicador de salud
  - Indicador discreto: "● Tyrion activo · openai · gpt-4o-mini · N procesados"
  - Punto verde si Anthropic/OpenAI, gris si mock; se actualiza con el polling cada 30s
- ✅ `backend/app/services/clasificador_openai.py` (NUEVO) — clasificador con OpenAI gpt-4o-mini
  - Para PDFs: extrae texto con pdfplumber primero (ruta barata); fallback a visión si falla
  - Para imágenes: siempre visión (base64 en la petición)
  - Mismo contrato que ClasificadorDocumental (devuelve `ResultadoClasificacion`)
  - Log: "Clasificador OpenAI (texto|visión) procesó X → tipo Y (confianza Z)"
- ✅ `backend/app/services/clasificador.py` (modificado) — auto-selección en `ClasificadorDocumental`
  - Orden de prioridad: OpenAI (si `OPENAI_API_KEY`) → Anthropic (si `ANTHROPIC_API_KEY`) → mock
  - Sin cambios en la interfaz `clasificar()` — transparente para el pipeline
- ✅ `backend/app/api/control.py` (ampliado) — `GET /api/salud`
  - Devuelve: `{ activo, clasificador ("openai"|"anthropic"|"mock"), modelo, procesados_hoy, ultima_actividad }`
- ✅ `backend/app/core/config.py` (ampliado) — `openai_api_key` y `clasificador_openai_model`
- ✅ `backend/requirements.txt` — añadido `openai>=1.0.0` y `pdfplumber>=0.11.0`
- ✅ `backend/.env.example` — documentadas `OPENAI_API_KEY` y `CLASIFICADOR_OPENAI_MODEL`
- ✅ `tools/generar_docs_demo.py` (NUEVO) — genera 8 PDFs mínimos en /tmp/tyrion_demo/
  - Trámite 1: transferencia completa (CTI + 620 + DNI + contrato) → listo_dgt
  - Trámite 2: transferencia incompleta (CTI + DNI, falta 620 y contrato) → aviso gestoría
  - Trámite 4: matriculación (solicitud + ficha técnica)
- ✅ 21 tests nuevos
  - `test_carga.py` (7): crear trámite, subir documento, resultado completo/incompleto, 404s
  - `test_clasificador_openai.py` (8): texto PDF, fallback visión, imagen, discrepancia, JSON inválido
  - `test_salud.py` (6): estructura, campos, mock sin keys, openai con key
- ✅ Suite acumulada: **221 pasando, 5 skipped, 0 fallos**

### Sesión 12 — Reescritura de carga manual con lógica correcta (16/06/2026)

**Problema corregido**: la carga de la sesión 11 (1) pedía al usuario declarar el tipo de trámite (viola la premisa), (2) no conectaba con la Pantalla de Control, (3) fallaba con pdfplumber en Docker.

**Principio rector**: el administrativo arrastra documentos; Tyrion deduce todo lo demás. El tipo de trámite NO lo declara el usuario — lo infiere el clasificador viendo los documentos.

- ✅ **TAREA 1 — pdfplumber → PyMuPDF (fitz)**
  - `requirements.txt`: `pdfplumber` reemplazado por `pymupdf>=1.24.0`
  - `clasificador_openai.py`: `_extraer_texto_pdf()` usa `fitz` (wheels manylinux self-contained, sin dependencias nativas problemáticas como cryptography/cffi)
  - `Dockerfile`: nota documentando que PyMuPDF no requiere libmupdf-dev
- ✅ **TAREA 2 — `carga.py` reescrito con lógica correcta**
  - `POST /api/carga/documentos` (multipart N archivos): clasifica cada uno, guarda en storage, devuelve `sesion_id` + lista clasificada. NO crea trámite todavía
  - `POST /api/carga/procesar` ({sesion_id, gestoria?, matricula?...}): deduce tipo, evalúa checklist con el tipo correcto, determina estado, prepara avisos, crea el trámite
  - `GET /api/carga/sesion/{id}`: estado de la sesión (docs subidos + trámite creado)
- ✅ `deduccion_tipo.py` (NUEVO) — `deducir_tipo_tramite(tipos)` 
  - Documento PRINCIPAL define el tipo: solicitud_matriculación→MATRICULACION, solicitud_baja→BAJA, CTI/contrato→TRANSFERENCIA
  - Señales de herencia (modelo 650, declaración herederos) → subtipo herencia
  - Respaldo por documentos secundarios; sin señal → revisión manual
- ✅ **TAREA 3 — `carga.html` reescrito (UX en 2 pasos)**
  - Paso 1: zona drag&drop grande sin formularios previos; cada doc muestra spinner→tipo+confianza en vivo; campos opcionales discretos (gestoría/matrícula) en `<details>`
  - Paso 2: tipo de trámite deducido + estado con color + lista de documentos/requisitos + aviso si faltan docs + "Ver en Pantalla de Control"
- ✅ **TAREA 4 — Trámites de carga conectados con la Pantalla de Control**
  - `registro_tramites.py` (NUEVO) — registro en memoria compartido entre carga y control
  - `_tramites_fuente()` combina trámites de carga manual + base (prueba/BD); `GET /api/tramites` y detalle los incluyen
  - Forma del trámite idéntica a TRAMITES_PRUEBA (sin distinción de origen en el frontend)
- ✅ **TAREA 5 — `/api/salud` con datos reales**
  - `procesados_hoy` = trámites creados hoy (registro); `ultima_actividad` = timestamp del último
- ✅ Tests
  - `test_deduccion_tipo.py` (11): CTI→TRANSFERENCIA, solicitud→MATRICULACION, herencia, respaldo, sin señal
  - `test_carga_v2.py` (10): subir→clasificar→procesar→deducir tipo→aparece en /api/tramites→cuenta en /api/salud
  - `test_clasificador_openai.py` actualizado a fitz; `test_carga.py` (sesión 11) eliminado
- ✅ Verificado end-to-end: 4 PDFs demo → tipo TRANSFERENCIA deducido → listo_dgt → visible en Pantalla Control
- ✅ Suite acumulada: **234 pasando, 5 skipped, 0 fallos**

### Fix puntual — GET /api/documentos/{doc_id}/extraccion para docs de carga (16/06/2026)
- ✅ Nuevo `backend/app/api/store.py` — `DOCUMENTOS_CARGA` dict compartido entre carga y documentos
- ✅ `carga.py` popula `DOCUMENTOS_CARGA` en `procesar_sesion()` con validez, campos y justificación
- ✅ `documentos.py` busca en `DOCUMENTOS_CARGA` como fallback tras `DOCUMENTOS_PRUEBA`
- ✅ `_tramite_o_404()` también busca en `registro_tramites` → `listar_documentos` funciona para trámites manuales
- ✅ 4 tests nuevos — `backend/tests/test_documentos_carga.py`
- ✅ Suite acumulada: **238 pasando, 5 skipped, 0 fallos**

### Fix puntual — ClasificadorOpenAI nunca manda PDF a visión (16/06/2026)
- ✅ `clasificador_openai.py` — orden estricto PDF: texto → chat | sin texto → PNG via fitz → visión image/png
- ✅ `_extraer_texto_pdf(contenido: bytes)` recibe bytes (no ruta), usa `fitz.open(stream=...)`
- ✅ Nueva función `_pdf_primera_pagina_png(contenido: bytes)` convierte primera página a PNG (dpi=150)
- ✅ `_clasificar_vision_bytes(img_bytes, mime, ...)` reemplaza `_clasificar_vision(ruta, mime, ...)` — nunca acepta application/pdf
- ✅ Imágenes JPG/PNG → visión directamente con su MIME correcto
- ✅ 3 nuevos tests — `backend/tests/test_clasificador_openai_pdf.py` (PDF con texto, PDF sin texto, imagen JPG)
- ✅ Tests existentes `test_clasificador_openai.py` actualizados a nueva firma
- ✅ Suite acumulada: **241 pasando, 5 skipped, 0 fallos**

## ESTADO SESIÓN — 16/06/2026 (última)

### Próxima acción concreta
- **Sesión 13**: SMTP real + tabla `requisitos_tramite` en BD (v2 árbol condicional) + persistencia PostgreSQL del registro de carga manual

### Decisiones tomadas
- `docs/` es la referencia canónica de proceso
- El flujo real arranca desde la planilla (Tempus), no desde el email
- Emails sin match en planilla nunca se bloquean
- Sin `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` → clasificador mock automático
- CTI (Cambio Titularidad Individual) es el doc principal de TRANSFERENCIA, no permiso_circulacion
- Escalado al admin es SIEMPRE via timers (T+60), nunca directo en procesar_email()
- **El tipo de trámite NUNCA lo declara el administrativo — lo deduce Tyrion de los documentos**
- **Carga manual = vía estándar para papel (60% de gestorías), no una excepción**
- Extracción de texto PDF con PyMuPDF (fitz), no pdfplumber (robustez en Docker)
- Registro de carga manual en memoria (sesión 12); se migrará a PostgreSQL en sesión 13
