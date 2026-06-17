# CLAUDE.md — Contexto de Tyrion para Claude Code

Este archivo es leído automáticamente por Claude Code al abrir el repo.
Proporciona el contexto necesario para continuar la construcción sin explicar
el proyecto desde cero.

> **RAMA CANÓNICA: `main`.** Es la única fuente de verdad. La antigua rama de
> trabajo `claude/amazing-fermat-tpyer1` fue integrada a `main` el 16/06/2026
> (merge `28cfc83`) y queda solo como respaldo histórico. Trabajar SIEMPRE sobre `main`.

## Qué es Tyrion

Capa de inteligencia documental para el Colegio de Gestores (cliente Alfa-Pyme).
Gestiona trámites de vehículos ante DGT para 70 gestorías. ~200 trámites/día
(170 transferencias + 30 matriculaciones). SLA: cierre en el día.

## Stack

FastAPI (Python 3.12) + PostgreSQL 15. Clasificación documental con **OpenAI
gpt-4o-mini** en producción (`clasificador_openai.py`); existe también un
clasificador Claude (`clasificador.py`). Deploy: Hostinger KVM2 vía Docker Compose.

- VPS: `187.127.233.43`, proyecto en `/root/tyrion/tyrion`
- Contenedores: `tyrion-api`, `tyrion-worker`, `tyrion-db`
- Arranque: `git checkout main && git pull && docker compose --env-file backend/.env up --build -d`

## Principios de diseño — NO negociables

1. La **validez de un documento vive en el vínculo documento-trámite**
   (`documento_tramite`), NUNCA en el documento. Un mismo PDF puede ser VALIDO
   en un trámite y EVIDENCIA_COMPATIBLE en otro.

2. **Evidencia compatible ≠ documento válido.** Un Modelo 620 no sustituye
   un Permiso de circulación aunque estén relacionados.

3. **Orden de escalado obligatorio:** (1) Tyrion resuelve por sus medios →
   (2) si falta documentación pide a la GESTORÍA (mensaje preparado, reintentos
   dentro del SLA) → (3) solo si la gestoría no responde o el caso se traba,
   escala al ADMINISTRATIVO. El administrativo es el último recurso.

4. **Mensaje preparado ≠ mensaje enviado.** El estado PREPARADO existe hasta que
   haya integración de envío real confirmada.

5. **Tyrion prepara; el humano presenta.** La presentación a DGT requiere paso
   humano. Sin integración electrónica en v1.

6. **Estado del DOCUMENTO ≠ estado del TRÁMITE.** Que todos los documentos
   cargados sean VALIDO no implica que el trámite avance: el motor de cotejo
   evalúa el checklist completo del tipo/subtipo. Si hay requisitos faltantes,
   el trámite queda en "Pendiente gestoría" aunque cada documento sea válido.

## Estado actual (17/06/2026)

- ✅ Schema PostgreSQL — `backend/migrations/`
- ✅ Clasificador OpenAI (prod) — `backend/app/services/clasificador_openai.py`
- ✅ Clasificador Claude (alt) — `backend/app/services/clasificador.py`
- ✅ Catálogo del dominio DGT (tipos, familias, subtipos, checklist) — `catalogo_documental.py`
- ✅ Motor de cotejo — `backend/app/services/motor_cotejo.py`
- ✅ Pipeline end-to-end — `backend/app/services/pipeline.py`
- ✅ Cruces multi-documento — `cruces.py`, `cruce_planilla.py`
- ✅ Ingesta email/planilla — `ingesta_email.py`, `ingesta_planilla.py`, `watcher_planilla.py`
- ✅ Pantalla Control (macro-estados) — `backend/static/`
- ✅ Suite de tests (~241 pasando) — `backend/tests/`

## Frente de trabajo abierto: calidad de EXTRACCIÓN del clasificador

El tipo de documento se clasifica bien, pero la EXTRACCIÓN de campos falla:
documentos con confianza ALTA y `datos_extraidos` vacío o incompleto. Defectos:

1. **Falta `CAMPOS_REQUERIDOS` por tipo** en `catalogo_documental.py`: no se
   define qué campos son obligatorios extraer de cada tipo de documento.
2. **Confianza desacoplada de extracción**: `_parsear_respuesta` (en ambos
   clasificadores) acepta `datos_extraidos: {}` con confianza ALTA sin penalizar.
   Regla pendiente: si faltan campos obligatorios del tipo → bajar confianza y
   marcar `requiere_validacion_humana`.
3. **Prompt de extracción vago**: la instrucción pide "datos clave" genéricos;
   debe pedir campos específicos por tipo detectado.
4. **`AVISO_1 · undefined` en la UI**: schema de avisos incompleto (revisar
   `pipeline.py` + `backend/static/`).
5. **Falta QA sistémico de extracción**: tests que validen extracción real de
   campos por familia documental (CTI, modelo_620, anexo_650, dni, ficha técnica).

## Realidad operativa (confirmada con cliente, sesión 2)

- 60% documentación física (papel), 40% email; una sola cuenta de email recibe docs.
- Tempus: las gestorías cargan trámite y documentos; fuente única a futuro, SIN API hoy.
  Estados Tempus confirmados: PENDIENTE / EN_REVISION / PRESENTADO / FINALIZADO.
- Planilla: exportada manualmente desde Gestión Transporte cada mañana.
- Confusión más frecuente: gestoría dice "Permiso", envía Modelo 620.
- DGT entrega comprobante físico al recibir expediente → campo `num_comprobante_dgt`.

## Comandos útiles

```bash
cd backend
pip install -r requirements.txt
pytest                       # todos los tests
pytest -v -k clasificador    # solo clasificador
pytest -v -k cotejo          # solo motor de cotejo
```

## Variables de entorno necesarias (backend/.env)

```
DATABASE_URL=postgresql+asyncpg://tyrion:tyrion@db:5432/tyrion
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```
