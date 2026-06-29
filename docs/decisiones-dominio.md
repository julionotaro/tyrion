# Decisiones de dominio

Correcciones y reglas del dominio de tramites de trafico, surgidas del trabajo
con documentacion real y de reuniones con la administracion del Colegio. El
conocimiento de dominio del personal real supera a las suposiciones.

## Documentos y campos

- **CTI (Cambio de Titularidad) NO contiene bastidor.** El bastidor solo aparece
  en el modelo 620 y en el anexo 650. No exigir cruce de bastidor contra CTI.
- **CTI y modelo 620 deben extraer DNI/NIF de adquirente y transmitente**, no solo
  los nombres. Sin el DNI extraido no se puede cotejar identidad.
- **Campo CET = "NO" significa ausencia de CET.** Debe normalizarse a vacio para
  que la evaluacion de completitud lo trate como faltante, no como presente.
- **Permiso de circulacion es de salida (output), no de entrada.** No se exige
  como documento aportado.

## Transferencia por herencia

- Documento central: **declaracion responsable de persona fisica**, no el CTI.
- Cruces de datos entre: declaracion responsable (matricula, nombre, DNI, firma),
  modelo 650 (sujeto pasivo/heredero, causante, representante), anexo 650
  (matricula, bastidor) y certificado de defuncion (identidad del fallecido, si
  el sistema lo pide).

## Cotejo de datos (motor de cruce)

- Todos los tramites cruzan **todos** sus datos compartidos entre documentos, no
  solo presencia de tipo. Esa es la finalidad del sistema.
- Identidad por DNI/NIE/matricula/bastidor: discrepancia = **CRITICA** (bloquea).
- Nombres: **ADVERTENCIA** (no bloquea). Matching tolerante a orden invertido y
  abreviaturas; solo marca discrepancia cuando los nombres realmente no coinciden.

## Planillas y conciliacion

- **Conteo de operaciones por matricula unica.** Las cadenas de intervinientes
  comerciales (INTERVIENE COM / ENTREGA A COM) comparten matricula = 1 operacion.
- **Num. Presentacion de la planilla = identificador de gestoria**, no de operacion.
- Planilla de transferencias NO trae bastidor; la de matriculacion si.
- Cruce planilla<->expediente: transferencias por matricula; matriculaciones por
  matricula + bastidor.
- Hoja de caja: se muestra completa (incluye tipos fuera de alcance como duplicado
  y canje), pero solo se exige cotejo documental en transferencias y matriculaciones.

## Pendiente de confirmacion administrativa

- Documentos habilitantes para matriculacion y baja.
- Datos exactos del recibo DGT.
- Tiempos reales de procesamiento de tramites.
