# FLUJO OPERATIVO ESTANDARIZADO — Oficina de Trámites de Vehículos
**Colegio de Gestores de Pontevedra · Proyecto Tyrion**
**Fuente:** documentación operativa real de la oficina + entrevista sesión 1.

> **Propósito.** Formaliza el proceso real de la oficina de principio a fin. Es la arquitectura que Tyrion debe replicar. Corrige el modelo previo, que arrancaba erróneamente en el email.

---

## 1. VISIÓN GENERAL — el día de la oficina

```
PRIMERA HORA          DURANTE EL DÍA              CIERRE EN EL DÍA (SLA)
─────────────         ──────────────              ──────────────────────
Exportar planillas  → Recibir emails gestorías  → Validar trámites completos
de Tempus             Cruzar c/ planilla          Escalar incompletos
(universo del día)    Cotejar documentación       Imprimir / cerrar
```

El SLA es **cierre en el día**. Todo lo que entra debe quedar resuelto (validado o escalado) antes del cierre.

---

## 2. FASE 1 — APERTURA: exportar el universo del día

A primera hora, el administrativo exporta de **Tempus / Gestión Tráfico** las planillas de trámites que las gestorías ya cargaron:

| Planilla | Familia | Campos clave |
|---|---|---|
| **Relación de Transmisiones** | Transferencias | Nº presentación, matrícula, tasa, Adq.NIF, razón social, nombre adquirente, tipo transmisión |
| **Relación de Matrículas** | Matriculaciones | Nº presentación, matrícula, bastidor, primer/segundo apellido, nombre, fecha presentación, DGT |

Esta planilla es el **universo de trabajo cerrado del día**: define qué trámites existen y deben resolverse. Nada que no esté en la planilla es trabajo del día (salvo excepción a confirmar en sesión 2).

**En Tyrion:** nueva entidad `planilla_dia`, con filas `tramite_planificado`. Es el primer paso del pipeline, antes de procesar cualquier email.

---

## 3. FASE 2 — INGESTA: emails de las gestorías

Durante el día, cada gestoría envía por email la documentación de sus trámites. El mismo material puede descargarse también de Tempus.

Por familia, la documentación típica:

**Transferencia (compraventa):** Relación de Transmisiones + CTI + Modelo 620
**Transferencia (herencia):** CTI herencia + Declaración responsable + Modelo 650 + Anexo 650 + Certificado de defunción
**Matriculación:** Relación de Matrículas + Solicitud + Ficha técnica (BL/TIT) + comprobante IVTM + (según caso) impuesto matriculación, DUA, documentación extranjera

**En Tyrion:** el módulo de ingesta IMAP ya existe. Lo nuevo: cada email se asocia a una fila de la planilla, no genera un trámite huérfano.

---

## 4. FASE 3 — CRUCE: email contra planilla

Cada email entrante se cruza contra la fila correspondiente de la planilla del día.

- **Clave de cruce primaria:** número de bastidor (en Tempus se busca por los últimos 4 dígitos).
- **Claves secundarias:** matrícula, NIF del adquirente, nº de expediente.

Resultado del cruce:
- **Match** → la documentación se adjunta a esa fila; pasa a cotejo.
- **Sin match** → email sin trámite planificado (a definir en sesión 2: ¿se espera, se rechaza, se crea?).

**En Tyrion:** función `cruzar_email_con_planilla(email, planilla_dia)` por bastidor.

---

## 5. FASE 4 — VALIDACIÓN EN TEMPUS Y COTEJO

Con la documentación asociada a la fila, se valida.

### 5.1 Determinar la vía
- **Telemática** (TIPO A = @ en filtro Tempus) → valida la oficina.
- **No telemática** (histórico ART.11 RD982/2024, ciertos agrícolas) → va a Jefatura.

### 5.2 Resolver el checklist condicional
Según familia + subtipo + origen + tipo de vehículo + naturaleza de las partes, se resuelve la lista de requisitos (ver Matriz Documental §4-§6).

### 5.3 Cotejar documento a documento
Cada documento recibido se clasifica:
- **VÁLIDO** — es el documento correcto y sus datos cuadran.
- **EVIDENCIA COMPATIBLE** — acredita pero no es el exacto pedido → pide a gestoría.
- **RECHAZADO** — irrelevante o incorrecto.
- **NO APLICA** — no requerido para este subtipo.

### 5.4 Cruces multi-documento (los datos deben cuadrar entre sí)
- **Transferencia:** CET del CTI = CET del 620; bastidor consistente.
- **Herencia:** causante (650) = fallecido (defunción) = transmitente (CTI); vehículo en Anexo 650.
- **Matriculación:** bastidor consistente en solicitud + ficha técnica + IVTM + impuesto matriculación.

### 5.5 Validar contra ficha técnica (TIT) en Tempus
Campo P.2 → tomar el valor más alto (el primero). Campo P.3 → revisar también observaciones.

---

## 6. FASE 5 — RESOLUCIÓN: el principio de escalado

```
            ┌─────────────────────────────┐
            │  ¿Documentación completa     │
            │  y todos los cruces OK?      │
            └───────────┬─────────────────┘
                  SÍ    │    NO
          ┌─────────────┘    └──────────────┐
          ▼                                  ▼
   VALIDAR el registro              Tyrion PIDE A GESTORÍA
   (telemático) o enviar            (mensaje automático)
   a Jefatura (no telem.)                    │
          │                          T+0  aviso 1
          ▼                          T+30 aviso 2
   Marcar distintivos                T+60 escalar al ADMINISTRATIVO
   Imprimir / cerrar                         │
                                             ▼
                              El administrativo es el ÚLTIMO
                              recurso, nunca el primero
```

**Tiempos confirmados (sesión actual):** aviso 1 a los 0 min, aviso 2 a los 30 min, escalado al administrativo a los 60 min. (Pendiente validar valores reales por familia en sesión 2.)

### 6.1 Validación telemática (caso estándar)
Por defecto vienen marcados Tarjeta tipo A, Impuesto Municipal e Impuesto de Matriculación. Ajustar según reglas condicionales (remolque sin IM, etc.). Validar el registro.

### 6.2 No telemática
Cargar en nube para que lo gestione Jefatura.

### 6.3 Cierre administrativo
Tras validar: marcar/obtener distintivos medioambientales, imprimir, guardar cajetín. La hoja de caja registra las tasas del Colegio por expediente.

---

## 7. MAPA DEL FLUJO A LOS MÓDULOS DE TYRION

| Fase | Módulo Tyrion | Estado |
|---|---|---|
| 1 — Apertura / planilla | Ingesta de planilla (NUEVO) | 🔜 pendiente |
| 2 — Ingesta emails | `ingesta_email.py` | ✅ existe |
| 3 — Cruce email↔planilla | `cruce_planilla.py` (NUEVO) | 🔜 pendiente |
| 4 — Checklist condicional | `motor_cotejo.py` refactor + `catalogo_documental.py` | ✅ completado sesión 6 |
| 4 — Cruces multi-doc | `cruces.py` (NUEVO) | ✅ completado sesión 6 |
| 5 — Vía telem/no telem | flag en pipeline | 🔜 pendiente |
| 5 — Cotejo documento | `motor_cotejo.py` | ✅ existe |
| 6 — Escalado | `pipeline.py` timers | ✅ existe |
| 6 — Pantalla / cierre | Pantalla Control + split-view | ✅ existe |

---

## 8. DIFERENCIAS CLAVE CON EL MODELO PREVIO DE TYRION

| Modelo previo | Modelo corregido (este flujo) |
|---|---|
| El trámite nace del email | El trámite nace de la planilla; el email lo completa |
| Cruce por matrícula | Cruce por bastidor (últimos 4 dígitos) |
| Checklist fijo por tipo | Checklist condicional (árbol de decisión) |
| Cotejo documento a documento aislado | Cotejo + cruces multi-documento que deben cuadrar entre sí |
| Una sola vía de validación | Telemática (oficina) vs no telemática (Jefatura) |
| Hoja de caja = irrelevante | Hoja de caja = comprobante de tasas del Colegio |

---

## 9. PENDIENTE DE CONFIRMAR EN SESIÓN 2

1. Formato exacto de exportación de la planilla (CSV / PDF / pantalla Tempus).
2. Clave real de cruce email↔planilla (bastidor vs matrícula vs expediente).
3. Qué hace la oficina con un email que no está en la planilla del día.
4. Tiempos reales de SLA por familia de trámite.
5. Frecuencia y número de recordatorios reales antes de escalar.
6. Lista cerrada de estados ambiguos de Tempus.
7. Si reenvío corregido reemplaza o convive con la versión anterior.
8. Qué se imprime exactamente al cerrar cada familia de trámite.
