Contexto: Repo julionotaro/tyrion, rama main. Lee CLAUDE.md.
Cotejo de datos universal entre todos los documentos de un trámite. Hoy el
sistema valida presencia de tipo de documento pero NO cruza los datos entre
documentos — esa es la finalidad central del sistema. Alcance: TRANSFERENCIA
simple y TRANSFERENCIA herencia. Matriculación y baja quedan como TODO.

El prompt del clasificador se autogenera desde CAMPOS_REQUERIDOS +
CAMPOS_EXTRA_EXTRACCION en catalogo_documental.py. Para que extraiga un campo
nuevo basta añadirlo a una de esas tablas — NO se edita texto de prompt.
Identidad se cruza por DNI/NIE (CRÍTICA). Nombres se cruzan como ADVERTENCIA con
matching tolerante a orden y abreviaturas (no bloquean listo_dgt).

CAMBIO 1 — Campos de extracción nuevos en catalogo_documental.py
En CAMPOS_EXTRA_EXTRACCION añadir:
  D.CTI: "bastidor" (muchos CTI no lo traen → null es correcto).
  D.MODELO_650: "nombre_sujeto_pasivo", "nombre_causante", "representante",
    "matricula", "bastidor".
  D.DECLARACION_RESPONSABLE_FALLECIMIENTO: "bastidor".
  Verificar que CERTIFICADO_DEFUNCION ya tiene nombre_fallecido, dni_fallecido;
  ANEXO_650 ya tiene matricula, bastidor, valor_vehiculo;
  DECLARACION_RESPONSABLE_FALLECIMIENTO ya tiene nombre, dni, matricula.
Si CAMPOS_EXTRA_EXTRACCION no existe, crearlo dict[TipoDocumento, list[str]]={}.

CAMBIO 2 — Nuevo módulo motor_cruce.py
import unicodedata
from dataclasses import dataclass
from enum import Enum

class Criticidad(str, Enum):
    CRITICA = "CRITICA"
    ADVERTENCIA = "ADVERTENCIA"

@dataclass
class ReglaCruce:
    tipo_a: str; campo_a: str; tipo_b: str; campo_b: str
    label: str
    criticidad: Criticidad = Criticidad.CRITICA
    normalizador: str = "texto"

Normalizadores puros:
  _norm_texto(v): strip, upper, colapsa espacios internos a uno.
  _norm_documento_id(v): quita espacios/guiones/puntos, upper.
  _norm_matricula(v): quita espacios/guiones, upper.
  _norm_bastidor(v): quita espacios, upper.
  _NORMALIZADORES = {"texto":_norm_texto, "documento_id":_norm_documento_id,
                     "matricula":_norm_matricula, "bastidor":_norm_bastidor}

Matching de nombres tolerante (orden, tildes, abreviaturas):
  def _tokens_nombre(v):
      s = "".join(c for c in unicodedata.normalize("NFKD", v or "")
                  if not unicodedata.combining(c))
      s = s.upper().replace(".", " ")
      return [t for t in s.split() if t]
  def _coincide_nombre(a, b):
      ta, tb = _tokens_nombre(a), _tokens_nombre(b)
      if not ta or not tb: return False
      corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
      usados = []
      for t in corto:
          m = next((u for u in largo if u not in usados and
                    (u == t or u.startswith(t) or t.startswith(u))), None)
          if m is None: return False
          usados.append(m)
      return True

CAMBIO 3 — Tabla REGLAS_CRUCE en motor_cruce.py
Claves tuple (familia, subtipo) usando .value de FamiliaTramite/SubtipoTramite.
C = Criticidad
("TRANSFERENCIA","ninguno"): [
  ReglaCruce("cti","matricula","modelo_620","matricula","Matrícula",C.CRITICA,"matricula"),
  ReglaCruce("cti","dni_adquirente","modelo_620","nif_adquirente","DNI adquirente",C.CRITICA,"documento_id"),
  ReglaCruce("cti","dni_transmitente","modelo_620","nif_transmitente","DNI transmitente",C.CRITICA,"documento_id"),
  ReglaCruce("cti","bastidor","modelo_620","bastidor","Bastidor",C.CRITICA,"bastidor"),
  ReglaCruce("cti","nombre_adquirente","modelo_620","nombre_adquirente","Nombre adquirente",C.ADVERTENCIA,"nombre"),
  ReglaCruce("cti","nombre_transmitente","modelo_620","nombre_transmitente","Nombre transmitente",C.ADVERTENCIA,"nombre"),
  ReglaCruce("cti","cet","modelo_620","cet","CET",C.ADVERTENCIA,"texto"),
  ReglaCruce("cti","fecha_matriculacion","modelo_620","fecha_matriculacion","Fecha matriculación",C.ADVERTENCIA,"texto"),
]
("TRANSFERENCIA","herencia"): [
  ReglaCruce("declaracion_responsable_fallecimiento","matricula","anexo_650","matricula","Matrícula",C.CRITICA,"matricula"),
  ReglaCruce("declaracion_responsable_fallecimiento","dni","modelo_650","dni_sujeto_pasivo","DNI heredero",C.CRITICA,"documento_id"),
  ReglaCruce("modelo_650","dni_causante","certificado_defuncion","dni_fallecido","DNI causante",C.CRITICA,"documento_id"),
  ReglaCruce("modelo_650","matricula","anexo_650","matricula","Matrícula (650/anexo)",C.CRITICA,"matricula"),
  ReglaCruce("declaracion_responsable_fallecimiento","nombre","modelo_650","nombre_sujeto_pasivo","Nombre heredero",C.ADVERTENCIA,"nombre"),
  ReglaCruce("modelo_650","nombre_causante","certificado_defuncion","nombre_fallecido","Nombre causante",C.ADVERTENCIA,"nombre"),
]
("MATRICULACION","ninguno"): [],  # TODO pendiente confirmación administrativa
("BAJA","ninguno"): [],           # TODO pendiente confirmación administrativa

CAMBIO 4 — cotejar_datos() en motor_cruce.py
def cotejar_datos(familia, subtipo, docs_por_tipo) -> list[dict]:
  Para cada regla de (familia, subtipo):
    - tipo_a o tipo_b ausente de docs_por_tipo → omitir (no aplica).
    - val_a/val_b vacío (None/"") → estado="incompleto", ok=False, sin aviso.
    - ambos presentes:
        if normalizador=="nombre": coincide = _coincide_nombre(val_a, val_b)
        else: fn=_NORMALIZADORES[normalizador]; coincide = fn(val_a)==fn(val_b)
        coincide → estado="ok", ok=True
        no → estado="discrepancia", ok=False,
             aviso=f"{label} no coincide entre {tipo_a} ({val_a}) y {tipo_b} ({val_b})."
  Verificación: {"campo": f"{tipo_a}_{campo_a}__{tipo_b}_{campo_b}", "label",
    "ok", "estado", "criticidad": criticidad.value,
    "vals":[{"doc":tipo_a,"val":val_a},{"doc":tipo_b,"val":val_b}], "aviso"?}
  Devuelve todas (ok, discrepancia, incompleto) para la UI.

CAMBIO 5 — EstadoChecklist en motor_cotejo.py
  + verificaciones: list[dict] = field(default_factory=list)
  + property verificaciones_fallidas: [v for v in verificaciones
        if v["estado"]=="discrepancia" and v["criticidad"]=="CRITICA"]
  completo: añadir "and not self.verificaciones_fallidas"
  debe_pedir_gestoria: añadir "or self.verificaciones_fallidas"
Solo discrepancia CRÍTICA bloquea. ADVERTENCIA e incompleto se muestran, no bloquean.

CAMBIO 6 — evaluar_checklist en motor_cotejo.py
Añadir parámetros familia: str = "" , subtipo: str = "ninguno". Tras el bucle:
  from app.services.motor_cruce import cotejar_datos
  docs_por_tipo = {tipo: (clf.datos_extraidos if hasattr(clf,"datos_extraidos") else {})
                   for tipo, clf in documentos_por_requisito.items()}
  fam = familia or _FAMILIA_DESDE_TIPO.get(tipo_tramite, "")
  if fam:
      estado.verificaciones = cotejar_datos(fam, subtipo, docs_por_tipo)

CAMBIO 7 — Eliminar verificar_identidad_transferencia
Borrar de motor_cotejo.py. grep en todo el repo; reescribir tests que la usaran
contra cotejar_datos.

CAMBIO 8 — carga.py
- procesar_sesion: pasar familia y subtipo a evaluar_checklist.
- _construir_tramite: + parámetro verificaciones: list[dict] | None = None,
  guardarlo bajo "verificaciones". Pasar verificaciones=estado.verificaciones.
- Si verificaciones_fallidas: poblar avisos_pendientes con cada v["aviso"].

CAMBIO 9 — correlacion.py
En adjuntar_documentos / re-cotejo: recomputar verificaciones con cotejar_datos
sobre el conjunto completo y guardar en tramite["verificaciones"]. Si hay
discrepancia CRÍTICA y el trámite estaba en listo_dgt → reabrir a
pendiente_gestoria + entrada en historial.

CAMBIO 10 — worker_email
Verificar que el trámite persistido vía email recibe "verificaciones" análogo a
carga.py. Si no, añadirlo.

Tests
- test_motor_cruce.py: _coincide_nombre tolerante (abreviado/invertido True,
  distinto False); _norm_documento_id("35.306.584-C")=="35306584C";
  transferencia simple DNI 53111222H vs 53111223H → discrepancia CRITICA;
  todo coincide → ok; campo en un solo doc → incompleto; herencia matrícula
  declaración≠anexo → discrepancia CRITICA; herencia sin certificado_defuncion
  → reglas de causante omitidas.
- test_estado_verificaciones.py: completo+discrepancia CRITICA → completo False;
  completo+solo ADVERTENCIA/incompleto → completo True.
- test_carga_2388klm.py: procesar_sesion con los 2 PDFs de 2388KLM (DNI
  adquirente discrepante) → estado "pendiente_gestoria", aviso de discrepancia.

Criterio de éxito: cd backend && python -m pytest tests/ -x -q verde.
Commit: feat: motor de cruce declarativo (transferencia simple + herencia)
Verificación manual:
  1. Cargar 2 PDFs de 2388KLM (DNI discrepante) → "Pendiente gestoría" + aviso.
  2. Herencia con matrícula distinta declaración vs anexo_650 → "Pendiente gestoría".
