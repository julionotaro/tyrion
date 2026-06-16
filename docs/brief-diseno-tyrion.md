# BRIEF DE DISEÑO VISUAL — Tyrion
**Para:** Equipo de Diseño del Estudio (UX Architect + Critic)
**Proyecto:** Tyrion · Colegio de Gestores de Pontevedra
**Tipo de entregable solicitado:** UI spec (sistema de diseño + arquitectura de pantallas), no implementación.

> **Nota sobre el alcance.** El Equipo de Diseño ya aprobó la arquitectura funcional de Tyrion (exec #56). Este brief pide específicamente la capa visual y de experiencia que faltó: sistema de color, tipografía, componentes, jerarquía y navegación. No re-diseñar la lógica funcional, que ya está validada.

---

## 1. Contexto del producto

Tyrion es una capa de inteligencia documental que automatiza el flujo de trámites de vehículos del Colegio de Gestores. Recibe documentación de 70 gestorías (~200 trámites/día), la clasifica, coteja contra checklists, pide lo que falta a las gestorías automáticamente, y solo escala al administrativo lo que no puede resolver.

**El producto se vende como solución entre sistemas y flujos mal organizados.** La interfaz debe transmitir orden, control y calma — lo contrario del caos que viene a resolver.

---

## 2. El usuario y su contexto

- **Quién:** administrativo de oficina de gestoría. No es técnico. Conoce profundamente el dominio de trámites DGT.
- **Dónde:** PC de escritorio en oficina. Pantalla grande. No móvil.
- **Cuánto:** 7+ horas al día mirando esta pantalla. Es su herramienta de trabajo principal.
- **Qué necesita:** ver de un vistazo qué trámites necesitan su atención, y confiar en que lo que Tyrion marca como resuelto está realmente resuelto.
- **Qué teme:** que se le escape un trámite y se pase el SLA (cierre en el día). Que la herramienta le mienta sobre el estado real.

**Implicación de diseño:** densidad de información alta pero legible. Jerarquía de urgencia clarísima. Cero decoración que distraiga. La estética es la de una herramienta profesional de trabajo intensivo, no la de una app de consumo.

---

## 3. Lo que NO debe ser

- No debe parecer una landing page ni tener "momentos hero".
- No debe usar la estética genérica de dashboard SaaS (cards con grandes números de colores, gráficos de torta decorativos).
- No debe priorizar lo bonito sobre lo legible.
- No debe esconder información detrás de clics innecesarios: el administrativo necesita ver mucho a la vez.

---

## 4. Arquitectura de pantallas solicitada

El Equipo debe diseñar el sistema visual para estas pantallas:

### 4.1 Navegación principal (menú)
Hoy solo existe la pantalla de Control. Faltan:
- **Control** — el día en curso (existe).
- **Trámites** — histórico buscable de todos los trámites.
- **Gestorías** — registro de las 70 gestorías con su ficha e historial.
- **Informes** — métricas del flujo (volumen, tiempos, % escalado).

### 4.2 Pantalla de Control (la principal)
- Los 6 macro-estados del trámite, con conteo y señal de urgencia.
- Tabla de trámites del día, filtrable.
- Panel de detalle de un trámite (documentos, historial, avisos).
- Split-view documental: documento + datos extraídos + validación por campo.

### 4.3 Indicador de salud del sistema
- Señal visible de que Tyrion está activo y procesando.
- Qué proveedor de IA usa, cuántos trámites procesó, última actividad.

### 4.4 Ficha de trámite (histórico)
- Vista completa de un trámite cerrado, con toda su documentación y timeline.

### 4.5 Ficha de gestoría
- Datos de contacto, historial de trámites, tasa de documentación incompleta.

---

## 5. Los 6 macro-estados (semántica de color)

El flujo del trámite. El color debe encodear el significado, no decorar:

1. **Recibido** — acaba de entrar, sin procesar aún.
2. **En revisión** — Tyrion está cotejando.
3. **Pendiente gestoría** — falta documentación, se pidió a la gestoría. ESTADO DE ALERTA.
4. **Listo DGT** — completo y validado, listo para presentar.
5. **En cadetería** — en camino físico a DGT.
6. **Cerrado** — trámite finalizado.

El estado "Pendiente gestoría" es el que demanda atención: debe destacar visualmente sin gritar.

---

## 6. Estados de validación documental (semántica de color)

Cada documento cotejado cae en uno de estos. Necesitan color propio, distinto del de los estados de trámite:

- **Válido** — es el documento correcto y sus datos cuadran.
- **Evidencia compatible** — acredita pero no es el exacto pedido; se pidió el correcto.
- **Rechazado** — irrelevante o incorrecto.
- **No aplica** — no requerido para este subtipo de trámite.

---

## 7. Principios de experiencia a respetar

- **El escalado es el último recurso.** La interfaz debe dejar claro que Tyrion intentó resolver solo y pedir a la gestoría antes de molestar al administrativo. El historial de cada trámite cuenta esa secuencia.
- **Transparencia de la automatización.** El administrativo debe poder ver POR QUÉ Tyrion tomó cada decisión (por qué clasificó así, por qué escaló, por qué cambió de estado). Genera confianza.
- **Acceso en pocos clics.** Las acciones frecuentes a un máximo de 2-3 clics.
- **Tono formal, español de España, sin tecnicismos.** El usuario es administrativo, no ingeniero.

---

## 8. Lo que se pide al Equipo de Diseño concretamente

Un documento de UI spec que incluya:
1. **Sistema de color** — paleta nombrada con semántica explícita (qué color = qué significado), funcionando para los 6 estados de trámite + 4 de validación + neutros.
2. **Tipografía** — familias y escala, pensadas para densidad y lectura prolongada.
3. **Componentes** — especificación de: tabla de trámites, badges de estado, panel de detalle, split-view, cards de métricas, navegación principal.
4. **Jerarquía visual** — cómo se prioriza la urgencia, cómo se distingue lo que necesita atención de lo que está en orden.
5. **Un elemento de firma** — el detalle visual que hace a Tyrion reconocible, apropiado para una herramienta profesional (no decorativo).

---

## 9. Material de referencia disponible

- `docs/flujo-operativo-estandarizado.md` — el proceso real de la oficina.
- `docs/matriz-documental-tramites.md` — los tipos de trámite y documentos.
- `docs/instructivo-operativo.md` — el lenguaje y los conceptos del dominio.
- Frontend actual en `backend/static/index.html` — funcional, base a mejorar.
