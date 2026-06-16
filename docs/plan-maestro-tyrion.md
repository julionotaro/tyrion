# PLAN MAESTRO — Camino a Tyrion presentable
**Proyecto Tyrion · Colegio de Gestores de Pontevedra**
**Contexto:** tras la primera demo en VPS, se identificaron 5 frentes de trabajo. Este documento los ordena por dependencia, no por urgencia percibida.

> **Premisa rectora del proyecto.** Tyrion se vende como solución entre sistemas y flujos mal organizados. Si en algún punto Tyrion *agrega* trabajo al administrativo (subir archivos, clasificar a mano, revisar lo que debería ser automático), traiciona su razón de ser. Cada decisión se valida contra esta premisa.

---

## Los 5 frentes (del feedback)

1. **Ingesta de datos** — cómo entran trámites y documentos sin generar trabajo.
2. **Validación y automatización rigurosas** — la lógica core: documentación por trámite, cruces entre documentos, cambios de estado y envíos automáticos. Con controles.
3. **Navegación completa** — histórico de trámites y documentos, registro de gestorías, informes.
4. **Estado de funcionamiento + OpenAI** — Tyrion conectado a un proveedor real y un indicador visible de que está vivo y procesando.
5. **Diseño visual y estructura** — pulido y arquitectura de la interfaz.

---

## El grafo de dependencias

```
                    ┌──────────────────────┐
                    │  SESIÓN 2 (cliente)   │
                    │  desbloquea casi todo │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
  ┌───────────────┐   ┌─────────────────┐   ┌──────────────────┐
  │ 1. INGESTA    │   │ 2. VALIDACIÓN   │   │ Datos reales de  │
  │ (canal real)  │   │ Y AUTOMATIZAC.  │   │ checklist y SLA  │
  └───────┬───────┘   └────────┬────────┘   └──────────────────┘
          │                    │
          │   ┌────────────────┘
          ▼   ▼
  ┌────────────────────┐
  │ 4. ESTADO + OpenAI │  ← parcialmente independiente
  │ (salud del sistema)│
  └─────────┬──────────┘
            │
            ▼
  ┌────────────────────┐      ┌────────────────────┐
  │ 3. NAVEGACIÓN      │      │ 5. DISEÑO VISUAL   │
  │ (histórico, etc.)  │◄─────│ (Equipo de Diseño) │
  └────────────────────┘      └────────────────────┘
```

**Lectura del grafo:**
- La **sesión 2** desbloquea ingesta (1) y los datos reales que necesita la validación (2).
- **OpenAI (parte de 4)** es independiente: se puede conectar hoy.
- **El indicador de salud (resto de 4)** depende de que la ingesta y la automatización funcionen, porque eso es lo que reporta.
- **Navegación (3)** y **diseño (5)** vienen al final: necesitan saber qué datos y qué flujos existen para no rehacerse.

---

## Orden de ejecución recomendado

### Fase 0 — Antes de la sesión 2 (ahora)
- [Yo] Documento de arquitectura de ingesta (explora opciones del punto 1).
- [Yo] Brief de diseño para el Equipo de Diseño (punto 5, bien hecho).
- [Code, independiente] Conectar OpenAI como clasificador real (parte de 4).

### Fase 1 — Sesión 2 con el administrativo
Resolver las incógnitas que condicionan todo:
- ¿Dónde deja Tempus las planillas? ¿Carpeta, descarga, pantalla?
- ¿Por qué canal exacto llegan los emails de las gestorías?
- Checklist real de documentos por tipo de trámite.
- Tiempos reales de SLA y de recordatorios.
- Estados ambiguos de Tempus.

### Fase 2 — Ingesta definitiva (punto 1)
Con el canal confirmado, construir la entrada real sin trabajo manual:
- Email IMAP funcionando de punta a punta.
- Planilla: que Tyrion la busque, no que el administrativo la suba.
- Asociación documento↔trámite automática.

### Fase 3 — Validación y automatización con controles (punto 2)
El core. Con datos reales del checklist:
- Árbol condicional alimentado por datos reales (no inventados).
- Cruces multi-documento verificados contra casos reales.
- Automatización end-to-end REAL: el mail sale, el estado cambia.
- Controles: tests de escenarios + panel de auditoría de cada acción automática.

### Fase 4 — Estado de salud + OpenAI productivo (punto 4)
- Indicador visible: "Tyrion activo · clasificador OpenAI · procesó N hoy".
- Log de actividad accesible.
- Alertas si algo falla (mail no enviado, clasificador caído).

### Fase 5 — Navegación completa (punto 3)
- Menú: Control (hoy) · Trámites (histórico) · Gestorías · Informes.
- Búsqueda y filtros sobre histórico.
- Ficha de gestoría con su historial.

### Fase 6 — Diseño visual definitivo (punto 5)
- Implementar la UI spec del Equipo de Diseño.
- Aplicar a todas las pantallas (no solo la de control).

---

## Controles de calidad transversales (todas las fases)

Para el punto 2 ("controles rigurosos"), tres capas que ya empezamos:

1. **Tests de escenarios de negocio** (200 tests hoy) — cada regla de negocio es un test.
2. **Panel de auditoría** — cada acción automática de Tyrion queda registrada y es visible: por qué cambió un estado, por qué envió un mail, por qué escaló.
3. **Validación manual estructurada** — checklist de 20-30 casos críticos que se verifican antes de cada entrega (lo preparo como pieza aparte).

---

## Qué NO hacer

- No construir los 5 puntos en paralelo: el punto 1 condiciona 2, 3 y 4.
- No diseñar la UI final (5) antes de saber qué pantallas y datos existen (3).
- No inventar el checklist de validación: debe venir de la sesión 2.
- No pedirle al administrativo que suba archivos si Tyrion puede ir a buscarlos.

---

## Estado actual como base

Lo ya construido que sostiene este plan:
- 200 tests pasando, 0 fallos.
- Motor de cotejo condicional (9 familias, cruces multi-doc).
- Pipeline con escalado correcto (gestoría primero, admin último).
- Ingesta IMAP + watcher de planilla (falta conectar a canales reales).
- Clasificador multi-proveedor (Anthropic/OpenAI/mock).
- Pantalla de control con split-view (falta pulir y completar navegación).
- Docker + PostgreSQL + demo en 1 comando.
