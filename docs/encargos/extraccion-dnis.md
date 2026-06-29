Contexto: Repo julionotaro/tyrion, rama main. Lee CLAUDE.md.
Corrección de extracción de DNIs en CTI y modelo_620, y validación del campo CET.

PROBLEMA QUE RESUELVE
El clasificador extrae transmitente/adquirente como nombres en texto libre pero no
extrae sus DNIs como campos separados. CAMPOS_REQUERIDOS ya los declara
(dni_adquirente, dni_transmitente en CTI; nif_adquirente, nif_transmitente en
modelo_620), pero el prompt de extracción no los pide explícitamente.
Además, el campo CET="NO" se trata como presente (string truthy) cuando en
realidad indica ausencia de CET — debe tratarse como vacío/nulo para que la
evaluación de completitud lo marque como faltante.

Documentos de referencia (texto plano):
  - CTI González Fernández: matrícula 5042HZM, adquirente MARIA DEL CARMEN
    CARBALLAL LORES / DNI 35306584C, transmitente JOSE MANUEL GONZALEZ
    FERNANDEZ / DNI 14958073T, CET=NO.
  - Modelo 620 González Fernández: matrícula 5042HZM, bastidor LKXHYA9820K111111,
    adquirente NIF 35306584C, transmitente NIF 14958073T, CET=NO.

CAMBIO 1 — Prompt de extracción CTI en clasificador_openai.py
Localizar el bloque de instrucciones de extracción para tipo "cti".
Añadir extracción explícita de:
  - dni_adquirente: DOI/DNI/NIF del adquirente (solo el número, sin nombre)
  - dni_transmitente: DOI/DNI/NIF del transmitente (solo el número, sin nombre)
  - nombre_adquirente: nombre completo del adquirente
  - nombre_transmitente: nombre completo del transmitente
Mantener el campo matricula. El campo cet debe extraerse como el valor literal
("NO", "SI", código alfanumérico) — el tratamiento de "NO" como ausencia se
hace en CAMBIO 3.

CAMBIO 2 — Prompt de extracción modelo_620 en clasificador_openai.py
Localizar el bloque de instrucciones de extracción para tipo "modelo_620".
Añadir extracción explícita de:
  - nif_adquirente: NIF del adquirente (solo número)
  - nif_transmitente: NIF del transmitente (solo número)
  - nombre_adquirente: nombre/razón social del adquirente
  - nombre_transmitente: nombre/razón social del transmitente
Mantener los campos existentes (matricula, importe, bastidor, cet, fecha_devengo).
El campo cet mismo tratamiento que CTI (valor literal).

CAMBIO 3 — Normalización de CET en catalogo_documental.py / evaluar_completitud_extraccion
En la función evaluar_completitud_extraccion, antes de evaluar si un campo está
presente, aplicar esta normalización para el campo "cet":

    valor = datos_extraidos.get(campo)
    if campo == "cet" and isinstance(valor, str) and valor.strip().upper() in ("NO", "N/A", "-", ""):
        valor = None  # tratar como ausente

Si valor es None o vacío tras la normalización → campo faltante.

CAMBIO 4 — CAMPOS_REQUERIDOS: añadir nif como requeridos en modelo_620
En _init_campos_requeridos(), actualizar la entrada de modelo_620:

    D.MODELO_620: [
        "matricula", "bastidor", "importe", "fecha_devengo", "cet",
        "nif_adquirente", "nif_transmitente",
    ],

Eliminar "transmitente" y "adquirente" (nombres en texto libre, no cotejeables).

CAMBIO 5 — CAMPOS_REQUERIDOS: nombres en CTI (informativos, no requeridos)
En _init_campos_requeridos(), la entrada de CTI ya tiene los DNIs. Añadir
nombre_adquirente y nombre_transmitente como campos extraídos pero NO en
CAMPOS_REQUERIDOS — son informativos para mostrar en UI, no bloquean validez.

CAMBIO 6 — motor_cotejo.py: cruce CTI↔modelo_620 por DNI en transferencia simple
(Este cambio queda subsumido por el encargo del motor de cruce declarativo;
si ya se implementó motor_cruce.py, omitir este CAMBIO 6 y dejar el cruce de
DNI a las reglas de REGLAS_CRUCE.)

Tests
- test_extraccion_cti.py: dado dni_adquirente="35306584C", dni_transmitente=
  "14958073T", matricula="5042HZM", cet="NO" → evaluar_completitud_extraccion
  devuelve incompleto con ["cet"] en faltantes.
- test_extraccion_620.py: dado nif_adquirente="35306584C", nif_transmitente=
  "14958073T", matricula="5042HZM", bastidor="LKXHYA9820K111111", importe="70.50",
  fecha_devengo="15/05/2026", cet="NO" → incompleto con ["cet"] en faltantes.

Criterio de éxito: cd backend && python -m pytest tests/ -x -q verde.
Commit: fix: extraccion DNIs en CTI/620 y validacion CET
