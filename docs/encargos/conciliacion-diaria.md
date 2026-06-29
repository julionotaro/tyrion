Contexto: Repo julionotaro/tyrion, rama main. Lee CLAUDE.md.
Módulo de Conciliación diaria: cruza tres fuentes por gestoría+día —
planilla (Tempus), documentación recibida (expedientes), hoja de caja (SAGE).
Vista nueva en el menú. Alcance cotejo: TRANSFERENCIA + MATRICULACION; resto
de tipos de la hoja de caja se muestran "fuera de alcance".

DECISIONES FIJAS
- Conteo de operaciones por MATRÍCULA única (cadenas de intervinientes
  "INTERVIENE/ENTREGA A COM" comparten matrícula = 1 operación).
- Núm.Presen. de la planilla = identificador de GESTORÍA, no de operación.
- Cruce planilla↔expediente: transferencias por matrícula; matriculaciones por
  matrícula+bastidor (la planilla de transferencias NO trae bastidor).
- Gestoría del expediente: email→remitente; manual→form (si vacío "(sin asignar)"
  no concilia).
- Planillas y hoja de caja entran como PDF.

CAMBIO 1 — gestorias.py: num_presentacion
+ campo num_presentacion: str = "" en dataclass Gestoria.
+ sembrar en _SEED números de demo:
    jlogistic3000→"00008", ruiz→"00005", lopez→"00006", martin→"00013",
    fernandez→"00027", carballal→"01413".
  Ajustar _cargar_seed, crear(), actualizar() (nuevo param num_presentacion).
+ def obtener_por_num_presentacion(num: str) -> dict | None.

CAMBIO 2 — ingesta_planilla.py: parser PDF
+ parse_planilla_pdf(contenido: bytes, fecha=None, fuente="tempus") -> PlanillaDia.
  Usar PyMuPDF (fitz). Detectar tipo por cabecera: "TRANSFE" → TRANSMISIONES;
  "COMP"/"Bastidor (E)" → MATRICULAS.
  Parsear por tokens (el número de fila va en su propia línea seguido de la fila):
    Transferencias: matrícula (regex [0-9]{4}[A-Z]{3} o EXXXXBXX), tasa (12 díg.),
      fecha, NIF adquirente, apellidos+nombre, tipo_transmision (NORMAL O SENC /
      INTERVIENE COM / ENTREGA A COM).
    Matriculaciones: matrícula, bastidor (VIN 17), apellidos, nombre, fecha.
  Capturar Núm.Presen. por fila → TramitePlanificado.
  Ignorar TOTAL:, "1 / N", cabeceras.
+ campo num_presentacion: str = "" en TramitePlanificado.
  Mantener parsers CSV existentes.

CAMBIO 3 — ingesta_hoja_caja.py (nuevo)
@dataclass LineaCaja: tipo_label:str; cantidad:int; total_linea:float
@dataclass HojaCaja: gestoria_nombre:str; fecha:date; lineas:list[LineaCaja];
  total:float; num_presentacion:str=""
+ parse_hoja_caja_pdf(contenido: bytes, fecha=None) -> HojaCaja (PyMuPDF).
+ MAPA_CAJA_A_FAMILIA:
    "tramitacion transferencia" → "TRANSFERENCIA"
    "matriculacion vehiculos"   → "MATRICULACION"
  Tipos no mapeados (duplicado, canje, conductores) → None = fuera de alcance.

CAMBIO 4 — conciliacion.py (nuevo)
  class EstadoConciliacion(str,Enum):
    CONCILIADO_OK; PENDIENTE_DOCUMENTACION; PENDIENTE_COTEJO;
    SIN_DECLARAR_PLANILLA; DUPLICADO_PLANILLA
  @dataclass FilaConciliada: matricula; bastidor; tipo_tramite; num_expediente;
    estado:EstadoConciliacion; tramite_id:str|None; estado_cotejo:str|None;
    intervinientes:int=1
  @dataclass DescuadreCaja: tipo_label; familia:str|None; cant_planilla:int;
    cant_caja:int; diferencia:int; fuera_alcance:bool
  @dataclass ConciliacionDia: gestoria_email; gestoria_nombre; fecha;
    filas:list[FilaConciliada]; descuadres:list[DescuadreCaja]; resumen:dict

  def conciliar(planillas, hoja, expedientes, gestoria_email, fecha) -> ConciliacionDia:
    # Cruce C: agrupar filas por matrícula. Operación = matrícula única.
    #   Filas idénticas (matrícula+NIF+tipo_transmision) repetidas → DUPLICADO_PLANILLA.
    #   Cadena de intervinientes (misma matrícula, distinto NIF/tipo) → 1 operación.
    # Cruce A: por operación → buscar expediente (transf por matrícula, matric por
    #   matrícula+bastidor). listo_dgt→CONCILIADO_OK; otro→PENDIENTE_COTEJO;
    #   sin match→PENDIENTE_DOCUMENTACION; expediente sin fila→SIN_DECLARAR_PLANILLA.
    # Cruce B: cant_planilla[familia]=matrículas únicas; vs hoja de caja;
    #   líneas fuera de alcance fuera_alcance=True.

CAMBIO 5 — api/conciliacion.py (nuevo router)
  POST /api/conciliacion/planilla   (multipart PDF + fecha)
  POST /api/conciliacion/hoja-caja  (multipart PDF + gestoria_email + fecha)
  GET  /api/conciliacion/{gestoria_email}/{fecha} → ConciliacionDia serializado
  POST /api/conciliacion/{gestoria_email}/{fecha}/avisar → avisos a
       PENDIENTE_DOCUMENTACION (reusar motor de avisos)
  Store en memoria por (gestoria|num_presentacion, fecha). Registrar router en main.py.

CAMBIO 6 — Frontend: vista "Conciliación"
En index.html, cuarta pestaña tras Gestorías. Selector gestoría+fecha; 3 tarjetas-
cifra (planilla/documentación/caja) con semáforo; tabla de filas con badge de
estado; panel "Cuadre de caja" (fuera_alcance en gris); botón "Avisar gestoría".
Paleta existente (verde-petróleo #0F6E56, gris papel #F5F4EF, JetBrains Mono).

Tests
- test_ingesta_planilla_pdf.py: 0109JSF aparece 3 veces (1 matrícula);
  matriculaciones 16 filas con bastidor.
- test_ingesta_hoja_caja.py: 7 transferencias, 3 matric., duplicado/canje familia None.
- test_conciliacion.py: 3 intervinientes misma matrícula → 1 fila intervinientes=3;
  fila sin expediente → PENDIENTE_DOCUMENTACION; listo_dgt con fila → CONCILIADO_OK;
  expediente sin fila → SIN_DECLARAR_PLANILLA; cuadre caja; "Duplicado" fuera_alcance.
- test_gestorias_num_presentacion.py: obtener_por_num_presentacion("00008").

Criterio de éxito: cd backend && python -m pytest tests/ -x -q verde.
Commit: feat: módulo de conciliación diaria planilla/documentación/hoja de caja
