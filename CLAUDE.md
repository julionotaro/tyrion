# CLAUDE.md — Contexto de Tyrion para Claude Code

Este archivo es leído automáticamente por Claude Code al abrir el repo.
Proporciona el contexto necesario para continuar la construcción sin necesidad
de explicar el proyecto desde cero.

## Qué es Tyrion

Capa de inteligencia documental para el Colegio de Gestores (cliente Alfa-Pyme).
Gestiona trámites de vehículos ante DGT para 70 gestorías. ~200 trámites/día
(170 transferencias + 30 matriculaciones). SLA: cierre en el día.

## Stack

FastAPI (Python 3.12) + PostgreSQL 15 + Claude API (Haiku para clasificación masiva,
Opus para conflictos y escalados). Deploy: Hostinger KVM2.

## Principios de diseño — NO negociables

1. La **validez de un documento vive en el vínculo documento-trámite** (tabla
   `documento_tramite`), NUNCA en el documento. Un mismo PDF puede ser VALIDO
   en un trámite y EVIDENCIA_COMPATIBLE en otro.

2. **Evidencia compatible ≠ documento válido.** Un Modelo 620 no sustituye
   un Permiso de circulación aunque estén relacionados.

3. **Orden de escalado obligatorio:**
   1. Tyrion intenta resolver por sus medios.
   2. Si falta documentación → Tyrion pide a la GESTORÍA (mensaje preparado,
      reintentos dentro del SLA).
   3. Solo si la gestoría no responde o el caso se traba → escala al
      ADMINISTRATIVO con resumen completo.
   El administrativo es el último recurso, no el primero.

4. **Mensaje preparado ≠ mensaje enviado.** El estado PREPARADO existe hasta que
   haya integración de envío real confirmada.

5. **Tyrion prepara; el humano presenta.** La presentación física a DGT siempre
   requiere paso humano. Sin integración electrónica en v1.

## Estado actual (15/06/2026)

- ✅ Schema PostgreSQL completo — `backend/migrations/001_initial_schema.sql`
- ✅ Clasificador documental con Claude API — `backend/app/services/clasificador.py`
- ✅ Catálogo del dominio DGT — `backend/app/services/catalogo_documental.py`
- ✅ 15 tests pasando — `backend/tests/test_clasificador.py`
- 🔜 Motor de cotejo (siguiente módulo)
- 🔜 Ingesta de email
- 🔜 Pantalla Control (6 macro-estados)
- 🔜 Cruce hoja de caja / SAGE

## Próximo módulo a construir: Motor de cotejo

Archivo destino: `backend/app/services/motor_cotejo.py`

Recibe un documento ya clasificado y decide su validez contra el checklist
del tipo de trámite (tabla `requisitos_tramite`). Devuelve:
- `VALIDO` — desbloquea ese requisito del trámite
- `EVIDENCIA_COMPATIBLE` — relacionado pero no suficiente
- `RECHAZADO` — no sirve / incorrecto para ese requisito
- `NO_APLICA` — no corresponde a este trámite

Si detecta un faltante o un rechazo → genera un mensaje a la gestoría
(estado PREPARADO), no escala al administrativo todavía.

## Datos de la entrevista relevantes

- Tipos de documento más comunes: permiso_circulacion, modelo_620, cti, dni
- Confusión más frecuente: gestoría dice "Permiso", envía Modelo 620
- El listado oficial de requisitos vive en: Reglamentación general de vehículos título IV
  (pendiente de cargar en tabla `requisitos_tramite` tras sesión 2)
- 4 estados de Tempus confirmados: PENDIENTE / EN_REVISION / PRESENTADO / FINALIZADO
- DGT entrega comprobante físico al recibir expediente → campo `num_comprobante_dgt`

## Comandos útiles

```bash
cd backend
pip install -r requirements.txt
pytest                   # correr todos los tests
pytest -v -k clasificador  # solo tests del clasificador
```

## Variables de entorno necesarias (.env)

```
DATABASE_URL=postgresql+asyncpg://tyrion:tyrion@localhost:5432/tyrion
ANTHROPIC_API_KEY=sk-ant-...
```
