# ARQUITECTURA DE INGESTA — Cómo entran los datos a Tyrion
**Proyecto Tyrion · Colegio de Gestores de Pontevedra**
**Propósito:** explorar y proponer cómo entran trámites y documentos sin generar trabajo nuevo. Guía de preguntas para la sesión 2.

> **Regla innegociable.** Tyrion NO puede pedirle al administrativo que suba archivos, exporte planillas o clasifique a mano. Si lo hace, agrega trabajo y contradice la premisa del proyecto. Tyrion va a buscar los datos; el administrativo no los trae.

---

## 0. REALIDAD CONFIRMADA EN SESIÓN 2 (15/06)

El flujo de entrada real de la oficina:

1. La **gestoría carga el trámite en Tempus** (datos básicos: matrícula, bastidor, tipo). Esto es lo que aparece en la planilla que se exporta desde "Gestión Transporte".
2. La documentación llega a la oficina por **email (40%) o físico/papel (60%)**.
3. La **gestoría también sube esa documentación a Tempus**.

**Implicación estratégica clave:** Tempus termina conteniendo TODO — datos del trámite Y documentos, ambos puestos por la gestoría. El email y el papel son hoy un canal **redundante** que existe solo porque Tempus todavía no es accesible para Tyrion.

**Conclusión:** la integración con Tempus es la solución definitiva (fuente única). El email/carga manual es el puente para esta etapa, no la arquitectura permanente.

Datos operativos confirmados:
- Una sola cuenta de email recibe la documentación. Acceso IMAP disponible tras implementar.
- La planilla se exporta manual desde Gestión Transporte → Trámites (Consulta) → filtros de fecha/tipo → descarga a Downloads → carpeta local.
- Tempus NO tiene exportación automática hoy. A futuro y avanzado el proyecto, se puede solicitar.
- Tempus implementará una página de subida de documentos en el futuro.
- Tyrion responderá a las gestorías desde una cuenta de correo propia (SMTP).
- Para la DEMO: carga manual de documentos de 3-4 trámites; Tyrion hace el resto.

---

## 1. Los dos tipos de dato y su origen

Hay que separar dos cosas que hoy se mezclan:

| Dato | Qué es | De dónde viene hoy |
|---|---|---|
| **El trámite** (metadatos) | Matrícula, bastidor, gestoría, tipo, titular | Lo cargan las gestorías en Gestión Tráfico/Tempus. El administrativo lo ve en la planilla del día. |
| **Los documentos** | CTI, 620, DNI, ficha técnica, etc. | Las gestorías los mandan por email (y a veces están en Tempus para descargar). |

Tyrion necesita ambos y cruzarlos. La planilla le dice "qué trámites existen hoy"; los emails le traen "la documentación de cada uno".

---

## 2. Las cuatro vías de entrada — análisis honesto

### Vía A — Email (documentos) — VÍA PRINCIPAL
**A favor:** las gestorías YA mandan los documentos por email. No hay que cambiar el comportamiento de nadie. Cero trabajo nuevo. Tyrion lee la bandeja, extrae adjuntos, clasifica.
**En contra:** hay que terminar la configuración IMAP (entrada) y SMTP (avisos de salida). Depende de saber qué cuenta de correo usa la oficina.
**Estado:** código IMAP construido; falta conectar a la cuenta real y activar SMTP.
**Pregunta sesión 2:** ¿qué cuenta de email recibe los documentos de las gestorías? ¿Es una sola cuenta o varias? ¿Se puede dar acceso IMAP?

### Vía B — Planilla de Tempus (trámites) — NECESARIA, SIN TRABAJO MANUAL
El reto: obtener la planilla del día sin que el administrativo exporte y suba un CSV.
Opciones, de mejor a peor:
1. **Tempus deja el listado en una carpeta/red** → Tyrion la lee con el watcher (ya construido). Cero trabajo. *Hay que confirmar si Tempus puede programar esa exportación.*
2. **El administrativo ya exporta la planilla igual cada mañana** (es parte de su rutina actual) → si ese archivo cae siempre en la misma carpeta, Tyrion lo toma de ahí. No es trabajo nuevo: ya lo hace.
3. **Tyrion lee la planilla del propio email** → si Tempus o el sistema la manda por correo, entra por la Vía A.
4. **Subida manual** → último recurso, solo si ninguna de las anteriores es posible.
**Pregunta sesión 2:** cuando abrís el día y sacás la planilla de Tempus, ¿qué hacés exactamente? ¿La descargás? ¿Queda en una carpeta? ¿Te la podés mandar por mail a vos misma? ¿Tempus puede dejarla sola en un sitio?

### Vía C — API de Gestión Tráfico / Tempus — IDEAL PERO BLOQUEADA
**A favor:** sería la entrada perfecta, datos estructurados en tiempo real.
**En contra:** no tenemos acceso, ni documentación, ni constancia de que exista una API. Tempus parece un sistema cerrado de escritorio.
**Estado:** descartada hasta tener información. No depender de esto.
**Pregunta sesión 2:** ¿Tempus tiene alguna forma de exportación automática, conexión, o webservice? (Probablemente no, pero hay que preguntarlo.)

### Vía D — Entrada manual — SOLO EXCEPCIONES
**A favor:** simple de construir, útil para casos raros (un trámite que llega por fuera del circuito normal).
**En contra:** si se vuelve la vía principal, Tyrion fracasó.
**Uso correcto:** una pantalla de "cargar trámite suelto" para el 1-2% de casos excepcionales, no para la operación diaria.

---

## 3. Arquitectura propuesta (sujeta a sesión 2)

```
TEMPUS (planilla)                    GESTORÍAS (documentos)
      │                                      │
      ▼                                      ▼
 [carpeta/red o mail]                  [email entrante]
      │                                      │
      ▼                                      ▼
 Watcher de Tyrion                     Ingesta IMAP
 (lee, no se le sube)                  (lee la bandeja)
      │                                      │
      └──────────────┬───────────────────────┘
                     ▼
            CRUCE POR BASTIDOR
       (la planilla define el universo;
        el email completa cada trámite)
                     ▼
            PIPELINE DE VALIDACIÓN
       (clasifica, coteja, cruza, decide)
                     ▼
        ┌────────────┴────────────┐
        ▼                         ▼
   Completo → validar      Falta algo → pide a
   estado: listo_dgt       gestoría (automático)
```

El principio: **dos flujos automáticos de entrada (planilla + email) que Tyrion va a buscar, nunca que le suben.** Se cruzan por bastidor. El administrativo no toca nada hasta que Tyrion escala un caso que no pudo resolver.

---

## 4. Lo que hay que construir según el resultado de la sesión 2

| Si la sesión 2 dice... | Entonces construimos... |
|---|---|
| "La planilla la exporto y queda en tal carpeta" | Watcher apuntando a esa carpeta (ya existe, solo configurar) |
| "La planilla me llega/puedo mandarla por mail" | Parser de planilla desde email (extender ingesta IMAP) |
| "Los docs llegan a tal cuenta de correo" | Conectar IMAP a esa cuenta + activar SMTP para avisos |
| "Tempus puede exportar solo a un sitio" | Watcher a ese sitio, ingesta 100% automática |
| "No hay forma automática para la planilla" | Pantalla de subida mínima (último recurso) + watcher para el futuro |

---

## 5. Una pantalla de carga SÍ hace falta — pero acotada

Aunque la entrada sea automática, conviene tener una pantalla de carga para:
- Casos excepcionales (trámite fuera del circuito).
- Re-procesar un documento que llegó mal.
- Demos y pruebas sin depender del correo real.

Debe ser **secundaria y opcional**, no la vía principal. Un botón "Cargar trámite manual" en el menú, no el centro de la app.

---

## 6. Preguntas concretas para la sesión 2 (ingesta)

1. ¿Qué cuenta de email recibe hoy los documentos de las gestorías? ¿Una o varias? ¿Se puede dar acceso de lectura (IMAP)?
2. Cuando exportás la planilla de Tempus a primera hora: ¿qué pasos hacés? ¿Dónde queda el archivo?
3. ¿Tempus puede programar una exportación automática a una carpeta o por correo?
4. ¿Los documentos también están disponibles para descargar en Tempus, o solo llegan por email?
5. ¿Hay una carpeta de red compartida en la oficina donde podrían caer las planillas?
6. ¿Qué formato tiene la planilla exportada? (CSV, Excel, PDF)
7. ¿Con qué cuenta de correo respondería Tyrion a las gestorías cuando falta documentación? (para SMTP)
8. ¿Cuántas gestorías mandan por email vs. cuántas dejan todo en Tempus?
