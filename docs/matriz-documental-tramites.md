# Matriz Documental — Trámites DGT
## Tyrion / Colegio de Gestores · Alfa-Pyme

> Fuente: Reglamentación general de vehículos título IV + entrevistas sesiones 1-5.
> Este documento es la referencia canónica para `resolver_checklist()` en `motor_cotejo.py`.

---

## §1. Familias y subtipos de trámite

### 1.1 TRANSFERENCIA
| Subtipo | Descripción |
|---------|-------------|
| `compraventa_particular` | Transmisión entre dos personas físicas |
| `compra_empresa` | Adquirente es persona jurídica (CIF) |
| `herencia` | Transmisión mortis causa |

### 1.2 MATRICULACION
| Subtipo | Origen |
|---------|--------|
| `nuevo` | Vehículo de primera matriculación en España |
| `usado` | Vehículo ya matriculado en España, se re-matricula |

Parámetro adicional `origen`:
- `espana` — fabricado/importado ya matriculado en España
- `ue` — procedente de otro Estado miembro UE
- `fuera_ue` — importado de país tercero
- `subasta` — adquirido en subasta pública

### 1.3 Otros trámites
| Familia | Descripción |
|---------|-------------|
| `BAJA` | Baja definitiva o temporal del vehículo |
| `CAMBIO_DOMICILIO` | Cambio de domicilio del titular |
| `DUPLICADO_CIRCULACION` | Duplicado del permiso de circulación |
| `DUPLICADO_FICHA` | Duplicado de la ficha técnica |
| `CONDUCTORES` | Alta/baja de conductores habituales |
| `PLACAS_VERDES` | Matrícula especial vehículo eléctrico |
| `PLACAS_ROJAS` | Matrícula provisional para traslado |

---

## §2. Checklist base por familia

### 2.1 TRANSFERENCIA — base común
- `permiso_circulacion`
- `modelo_620` (ITP)
- `dni` (de transmitente Y adquirente)
- `contrato_compraventa`

Subtipo `herencia` añade:
- `certificado_defuncion`
- `modelo_650` (Impuesto Sucesiones)
- `declaracion_herederos` o `testamento`
- `anexo_650` (relación de bienes)

Subtipo `compra_empresa` añade:
- `escritura_poder` (representación de la empresa)
- `cif` (o NIF de la persona jurídica)

### 2.2 MATRICULACION — base común
- `solicitud_matriculacion` (modelo oficial DGT)
- `ficha_tecnica`
- `ivtm` (Impuesto sobre Vehículos de Tracción Mecánica)
- `impuesto_matriculacion` (Impuesto Especial — excepto remolques)
- `dni`

Origen `ue` o `fuera_ue` añade:
- `documentacion_extranjera` (certificado de conformidad UE o declaración de importación)

### 2.3 BAJA
- `permiso_circulacion`
- `dni`
- `solicitud_baja` (modelo 05-B)

### 2.4 CAMBIO_DOMICILIO
- `permiso_circulacion`
- `dni`
- `justificante_domicilio` (empadronamiento o suministro)

### 2.5 DUPLICADO_CIRCULACION
- `dni`
- `solicitud_duplicado` (modelo 05-A)
- `justificante_pago` (tasa)

### 2.6 DUPLICADO_FICHA
- `dni`
- `solicitud_duplicado`
- `justificante_pago`

### 2.7 CONDUCTORES
- `permiso_circulacion`
- `dni` (del conductor a dar de alta/baja)

### 2.8 PLACAS_VERDES
- `permiso_circulacion`
- `ficha_tecnica`
- `certificado_homologacion_electrico`

### 2.9 PLACAS_ROJAS
- `dni`
- `justificante_pago`

---

## §3. Tipos de vehículo con impacto en el checklist

| Tipo vehículo | `tipo_vehiculo` | Efecto |
|---------------|-----------------|--------|
| Turismos / motos | `turismo` | Base estándar |
| Remolque / semirremolque | `remolque` | **Quitar** `impuesto_matriculacion` (exento por ley) |
| Tractor agrícola / maquinaria | `agricola` | **Añadir** `cartilla_agricola` |
| Vehículo histórico (ART.11 RD982/2024) | `historico` | Flag `no_telematico=True` (presentación física obligatoria en DGT) |

---

## §4. Naturaleza de las partes

| `naturaleza_partes` | Efecto |
|---------------------|--------|
| `particular` | DNI de cada parte |
| `empresa_adquirente` | CIF + escritura de poder del representante |
| `empresa_transmitente` | CIF del vendedor (no bloquea pero se registra) |

---

## §5. Reglas condicionales (árbol de decisión)

### §5.1 Motor de cotejo — reglas aplicables

```
resolver_checklist(familia, subtipo, origen, tipo_vehiculo, naturaleza_partes):
  base = checklist_base(familia)
  
  # §5.1.A — Remolque: exento de impuesto de matriculación
  if tipo_vehiculo == "remolque":
      base.remove("impuesto_matriculacion")
  
  # §5.1.B — Agrícola: requiere cartilla
  if tipo_vehiculo == "agricola":
      base.add("cartilla_agricola")
  
  # §5.1.C — Histórico: presentación física (flag, no modifica documentos)
  if tipo_vehiculo == "historico":
      flags["no_telematico"] = True
  
  # §5.1.D — Matriculación: vehículo nuevo vs. usado
  if familia == "MATRICULACION":
      if subtipo == "nuevo":
          base.remove_if_present("documentacion_extranjera")
      elif subtipo == "usado" and origen in ("ue", "fuera_ue"):
          base.add("documentacion_extranjera")
  
  # §5.1.E — Transferencia herencia
  if familia == "TRANSFERENCIA" and subtipo == "herencia":
      base.extend(["certificado_defuncion", "modelo_650", "declaracion_herederos", "anexo_650"])
  
  # §5.1.F — Empresa adquirente
  if naturaleza_partes == "empresa_adquirente":
      base.extend(["escritura_poder", "cif"])
  
  return base, flags
```

### §5.2 Vehículo nuevo (5.3A)
Sin documentación extranjera aunque subtipo sea `usado` si origen es `espana`.

### §5.3 Vehículo usado con origen UE (5.3B)
Requiere certificado de conformidad UE + baja del registro de origen.

---

## §6. Tipos documentales extendidos

Los siguientes tipos se añaden a `TipoDocumento` en `catalogo_documental.py`:

| Identificador canónico | Nombre |
|------------------------|--------|
| `solicitud_matriculacion` | Impreso oficial DGT matrícula |
| `ivtm` | Impuesto Vehículos Tracción Mecánica |
| `impuesto_matriculacion` | Impuesto Especial Matriculación |
| `documentacion_extranjera` | Cert. conformidad UE / declaración importación |
| `modelo_650` | Impuesto Sucesiones (herencias) |
| `certificado_defuncion` | Ya existía |
| `declaracion_herederos` | Notarial o acta de notoriedad |
| `anexo_650` | Relación de bienes hereditarios |
| `escritura_poder` | Poder notarial de representación de empresa |
| `cif` | Identificación fiscal persona jurídica |
| `solicitud_baja` | Modelo 05-B DGT |
| `solicitud_duplicado` | Modelo 05-A DGT |
| `justificante_domicilio` | Empadronamiento o factura suministro |
| `cartilla_agricola` | Registro maquinaria agrícola |
| `certificado_homologacion_electrico` | Homologación vehículo eléctrico |

---

## §7. Familias de trámite (enum)

```python
class FamiliaTramite(str, Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    MATRICULACION = "MATRICULACION"
    BAJA = "BAJA"
    CAMBIO_DOMICILIO = "CAMBIO_DOMICILIO"
    DUPLICADO_CIRCULACION = "DUPLICADO_CIRCULACION"
    DUPLICADO_FICHA = "DUPLICADO_FICHA"
    CONDUCTORES = "CONDUCTORES"
    PLACAS_VERDES = "PLACAS_VERDES"
    PLACAS_ROJAS = "PLACAS_ROJAS"
```

---

## §8. Subtipos (enum)

```python
class SubtipoTramite(str, Enum):
    # TRANSFERENCIA
    COMPRAVENTA_PARTICULAR = "compraventa_particular"
    COMPRA_EMPRESA = "compra_empresa"
    HERENCIA = "herencia"
    # MATRICULACION
    NUEVO = "nuevo"
    USADO = "usado"
    # Origen (parámetro separado)
    # ORIGEN_ESPANA / ORIGEN_UE / ORIGEN_FUERA_UE / ORIGEN_SUBASTA

class OrigenVehiculo(str, Enum):
    ESPANA = "espana"
    UE = "ue"
    FUERA_UE = "fuera_ue"
    SUBASTA = "subasta"

class TipoVehiculo(str, Enum):
    TURISMO = "turismo"
    REMOLQUE = "remolque"
    AGRICOLA = "agricola"
    HISTORICO = "historico"

class NaturalezaPartes(str, Enum):
    PARTICULAR = "particular"
    EMPRESA_ADQUIRENTE = "empresa_adquirente"
    EMPRESA_TRANSMITENTE = "empresa_transmitente"
```

---

## §9. Validaciones cruzadas multi-documento

### §9.1 Clave de cruce primaria
**Bastidor** (número VIN, 17 caracteres) es la clave primaria de cruce.
La matrícula puede cambiar; el bastidor es inmutable.

### §9.2 Cruce TRANSFERENCIA (`cruce_transferencia`)
| Campo | Doc A | Doc B | Acción si discrepan |
|-------|-------|-------|---------------------|
| CET (importe ITP) | CTI (valor de mercado) | Modelo 620 (base imponible) | EVIDENCIA: pedir justificación |
| Bastidor | Permiso circulación | CTI | RECHAZADO: fraude potencial |
| Bastidor | Permiso circulación | Modelo 620 | RECHAZADO |
| NIF transmitente | DNI | Permiso circulación (titular) | EVIDENCIA si difieren (¿titular != vendedor?) |

### §9.3 Cruce HERENCIA (`cruce_herencia`)
| Campo | Doc A | Doc B | Doc C |
|-------|-------|-------|-------|
| Nombre causante | Cert. defunción | Modelo 650 | CTI (titular del vehículo) |
| Vehículo en herencia | Bastidor en CTI | Bastidor en Anexo 650 | — |

Si causante del 650 ≠ fallecido en defunción → RECHAZADO
Si bastidor no aparece en Anexo 650 → RECHAZADO

### §9.4 Cruce MATRICULACION (`cruce_matriculacion`)
| Campo | Documentos que deben coincidir |
|-------|-------------------------------|
| Bastidor | Solicitud + Ficha técnica + IVTM + Impuesto matriculación |
| Potencia (kW) | Ficha técnica + IVTM (base de cálculo) |

---

## §10. Banderas de proceso

| Flag | Efecto |
|------|--------|
| `no_telematico` | Expediente debe presentarse físicamente; Tyrion lo marca para el administrativo |
| `requiere_revision_manual` | Cruce detectó discrepancia grave; bloquea hasta validación humana |
| `pendiente_documentacion_extranjera` | Matriculación con origen UE/fuera_ue sin doc. extranjera aún |

---

## §11. TODOs pendientes (sesión siguiente)

- [ ] Ingesta de planilla (Relación Transmisiones/Matrículas)
- [ ] Cruce email ↔ planilla (trámites del día vs. correos recibidos)
- [ ] Integración `resolver_checklist()` con tabla `requisitos_tramite` en BD
- [ ] Integración SMTP real para avisos
- [ ] Campo `no_telematico` en tabla `tramites` para históricos
