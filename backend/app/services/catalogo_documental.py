"""
Catálogo del dominio de trámites de vehículos ante DGT.

Incluye:
  - TipoDocumento: tipos documentales que Tyrion reconoce.
  - FamiliaTramite / SubtipoTramite / OrigenVehiculo / TipoVehiculo / NaturalezaPartes:
    parámetros del árbol de decisión de resolver_checklist().
  - TipoTramite / ValidezVinculo: enums del dominio (espejan los tipos SQL).
  - CHECKLIST_POR_TRAMITE: checklist base plano (fallback; sustituido por resolver_checklist).

Fuente: docs/matriz-documental-tramites.md + entrevistas sesiones 1-5.
"""
from enum import Enum


class TipoDocumento(str, Enum):
    """Tipos documentales reconocidos. El valor es el identificador canónico."""

    # Documentos clásicos (sesión 1)
    PERMISO_CIRCULACION = "permiso_circulacion"
    MODELO_620 = "modelo_620"                     # ITP (Impuesto Transmisiones Patrimoniales)
    CTI = "cti"                                    # Certificado de Características Técnicas / ITV
    DNI = "dni"
    CONTRATO_COMPRAVENTA = "contrato_compraventa"
    FICHA_TECNICA = "ficha_tecnica"
    JUSTIFICANTE_PAGO = "justificante_pago"
    CERTIFICADO_DEFUNCION = "certificado_defuncion"
    MANDATO_REPRESENTACION = "mandato_representacion"
    RELACION_TRANSMISIONES = "relacion_transmisiones"
    RELACION_MATRICULACIONES = "relacion_matriculaciones"
    HOJA_CAJA = "hoja_caja"

    # Matriculación (sesión 6 — matriz §6)
    SOLICITUD_MATRICULACION = "solicitud_matriculacion"   # impreso oficial DGT
    IVTM = "ivtm"                                          # Impuesto Vehículos Tracción Mecánica
    IMPUESTO_MATRICULACION = "impuesto_matriculacion"      # Impuesto Especial (exento en remolques)
    DOCUMENTACION_EXTRANJERA = "documentacion_extranjera"  # cert. conformidad UE / decl. importación

    # Herencia
    MODELO_650 = "modelo_650"                     # Impuesto Sucesiones
    DECLARACION_HEREDEROS = "declaracion_herederos"
    ANEXO_650 = "anexo_650"                       # relación de bienes hereditarios

    # Empresa
    ESCRITURA_PODER = "escritura_poder"           # poder notarial del representante
    CIF = "cif"                                   # identificación fiscal persona jurídica

    # Baja / duplicados / otros
    SOLICITUD_BAJA = "solicitud_baja"             # modelo 05-B DGT
    SOLICITUD_DUPLICADO = "solicitud_duplicado"   # modelo 05-A DGT
    JUSTIFICANTE_DOMICILIO = "justificante_domicilio"  # empadronamiento o factura suministro
    CARTILLA_AGRICOLA = "cartilla_agricola"       # registro maquinaria agrícola
    CERTIFICADO_HOMOLOGACION_ELECTRICO = "certificado_homologacion_electrico"

    DESCONOCIDO = "desconocido"


# ── Campos mínimos de extracción por tipo de documento ────────────────────────

CAMPOS_REQUERIDOS: dict["TipoDocumento", list[str]] = {}  # poblado tras definir el enum


def _init_campos_requeridos() -> dict:
    """Define los campos mínimos extraíbles obligatorios por tipo documental.

    Principio: solo campos que el clasificador PUEDE extraer del documento en sí
    y que son necesarios para el cotejo posterior. Para documentos puramente
    administrativos o de contexto (hoja_caja, relaciones, desconocido) se usa []
    porque no contienen datos estructurados que cotejemos por campo.
    """
    D = TipoDocumento
    return {
        # PENDIENTE FASE 3: confirmar si el doc principal de transferencia es cti o
        # permiso_circulacion (matriz §2.1 dice permiso_circulacion, instructivo B.1 dice cti)
        D.CTI: ["matricula", "titular", "bastidor", "cet"],
        D.PERMISO_CIRCULACION: ["matricula", "titular", "bastidor"],
        # cet: Código Electrónico de Transmisión — clave de cruce CTI↔620 (instructivo C.1 / matriz §9.2)
        # bastidor: clave de cruce estable (matrícula puede cambiar)
        D.MODELO_620: ["importe", "transmitente", "adquirente", "fecha_devengo", "cet", "bastidor"],
        D.DNI: ["nombre", "numero_documento"],
        D.CONTRATO_COMPRAVENTA: ["transmitente", "adquirente", "matricula", "precio"],
        D.FICHA_TECNICA: ["marca", "modelo", "bastidor"],
        D.JUSTIFICANTE_PAGO: ["importe", "referencia"],
        D.CERTIFICADO_DEFUNCION: ["nombre_fallecido", "fecha_defuncion"],
        D.MANDATO_REPRESENTACION: ["representado", "representante"],
        D.MODELO_650: ["causante", "heredero", "importe"],
        D.ANEXO_650: ["bastidor", "valor_vehiculo"],
        D.DECLARACION_HEREDEROS: ["causante", "herederos"],
        D.SOLICITUD_MATRICULACION: ["matricula", "titular"],
        D.IVTM: ["matricula", "importe"],
        D.IMPUESTO_MATRICULACION: ["matricula", "importe"],
        D.DOCUMENTACION_EXTRANJERA: ["bastidor", "pais_origen"],
        D.ESCRITURA_PODER: ["poderdante", "apoderado"],
        D.CIF: ["nombre_empresa", "numero_cif"],
        D.SOLICITUD_BAJA: ["matricula", "titular"],
        D.SOLICITUD_DUPLICADO: ["matricula", "titular"],
        D.JUSTIFICANTE_DOMICILIO: ["titular", "domicilio"],
        D.CARTILLA_AGRICOLA: ["titular", "matricula"],
        D.CERTIFICADO_HOMOLOGACION_ELECTRICO: ["bastidor", "homologacion"],
        # Documentos sin campos estructurados extraíbles para cotejo:
        D.RELACION_TRANSMISIONES: [],    # listado interno de gestoría, no tiene campos cotejeables
        D.RELACION_MATRICULACIONES: [],  # ídem
        D.HOJA_CAJA: [],                 # documento contable interno, no se coteja por campos
        D.DESCONOCIDO: [],               # tipo no reconocido, sin campos definidos
    }


def campos_requeridos(tipo: "TipoDocumento") -> list[str]:
    """Devuelve los campos mínimos de extracción para el tipo dado."""
    return CAMPOS_REQUERIDOS.get(tipo, [])


def evaluar_completitud_extraccion(
    tipo: "TipoDocumento",
    datos_extraidos: dict,
) -> tuple[bool, list[str]]:
    """Devuelve (esta_completo, campos_faltantes) para el tipo y los datos dados.

    Un campo se considera presente si existe en datos_extraidos con un valor
    no nulo y no vacío.
    """
    requeridos = campos_requeridos(tipo)
    if not requeridos:
        return True, []
    faltantes = [
        campo for campo in requeridos
        if not datos_extraidos.get(campo)
    ]
    return len(faltantes) == 0, faltantes


# ── Familias de trámite ────────────────────────────────────────────────────────

class FamiliaTramite(str, Enum):
    """Familia (tipo principal) del trámite. Parametriza resolver_checklist()."""
    TRANSFERENCIA = "TRANSFERENCIA"
    MATRICULACION = "MATRICULACION"
    BAJA = "BAJA"
    CAMBIO_DOMICILIO = "CAMBIO_DOMICILIO"
    DUPLICADO_CIRCULACION = "DUPLICADO_CIRCULACION"
    DUPLICADO_FICHA = "DUPLICADO_FICHA"
    CONDUCTORES = "CONDUCTORES"
    PLACAS_VERDES = "PLACAS_VERDES"
    PLACAS_ROJAS = "PLACAS_ROJAS"


class SubtipoTramite(str, Enum):
    """Subtipo dentro de la familia (ver matriz §1)."""
    # TRANSFERENCIA
    COMPRAVENTA_PARTICULAR = "compraventa_particular"
    COMPRA_EMPRESA = "compra_empresa"
    HERENCIA = "herencia"
    # MATRICULACION
    NUEVO = "nuevo"
    USADO = "usado"
    # Genérico (sin subtipo diferenciado)
    NINGUNO = "ninguno"


class OrigenVehiculo(str, Enum):
    """Procedencia del vehículo (relevante en matriculación). Matriz §1.2."""
    ESPANA = "espana"
    UE = "ue"
    FUERA_UE = "fuera_ue"
    SUBASTA = "subasta"


class TipoVehiculo(str, Enum):
    """Tipo de vehículo: impacta en documentos requeridos. Matriz §3."""
    TURISMO = "turismo"
    REMOLQUE = "remolque"      # exento de impuesto_matriculacion
    AGRICOLA = "agricola"      # requiere cartilla_agricola
    HISTORICO = "historico"    # flag no_telematico (ART.11 RD982/2024)


class NaturalezaPartes(str, Enum):
    """Naturaleza jurídica de transmitente/adquirente. Matriz §4."""
    PARTICULAR = "particular"
    EMPRESA_ADQUIRENTE = "empresa_adquirente"
    EMPRESA_TRANSMITENTE = "empresa_transmitente"


# ── Enums heredados (espejan tipos SQL) ───────────────────────────────────────

class TipoTramite(str, Enum):
    """Tipos de trámite. Espeja el enum SQL `tipo_tramite`. Usar FamiliaTramite en código nuevo."""
    TRANSFERENCIA = "TRANSFERENCIA"
    MATRICULACION = "MATRICULACION"
    BAJA = "BAJA"


class ValidezVinculo(str, Enum):
    """Validez de un documento respecto a un trámite. Vive en el vínculo, nunca en el documento.
    Espeja el enum SQL `validez_vinculo`."""
    VALIDO = "VALIDO"
    EVIDENCIA_COMPATIBLE = "EVIDENCIA_COMPATIBLE"
    RECHAZADO = "RECHAZADO"
    NO_APLICA = "NO_APLICA"


# ── Confusiones frecuentes ─────────────────────────────────────────────────────

CONFUSIONES_FRECUENTES = {
    TipoDocumento.PERMISO_CIRCULACION: [TipoDocumento.MODELO_620, TipoDocumento.CTI],
    TipoDocumento.MODELO_620: [TipoDocumento.PERMISO_CIRCULACION, TipoDocumento.JUSTIFICANTE_PAGO],
    TipoDocumento.CTI: [TipoDocumento.FICHA_TECNICA, TipoDocumento.PERMISO_CIRCULACION],
    TipoDocumento.MODELO_650: [TipoDocumento.MODELO_620],   # confusión herencia vs. ITP
}


# ── Checklist base plano (fallback; resolver_checklist() es la fuente viva) ──

CHECKLIST_POR_TRAMITE: dict[TipoTramite, list[str]] = {
    TipoTramite.TRANSFERENCIA: [
        "cti",
        "modelo_620",
        "dni",
        "contrato_compraventa",
    ],
    TipoTramite.MATRICULACION: [
        "solicitud_matriculacion",
        "ficha_tecnica",
        "ivtm",
        "impuesto_matriculacion",
        "dni",
    ],
    TipoTramite.BAJA: [
        "permiso_circulacion",
        "dni",
        "solicitud_baja",
    ],
}


# ── Rasgos distintivos para el clasificador ───────────────────────────────────

RASGOS_DISTINTIVOS = {
    TipoDocumento.PERMISO_CIRCULACION: (
        "Documento oficial DGT que autoriza la circulación del vehículo. "
        "Contiene matrícula, titular, marca/modelo, fecha de matriculación. "
        "Encabezado 'Permiso de Circulación' o 'Tarjeta de Inspección Técnica'."
    ),
    TipoDocumento.MODELO_620: (
        "Formulario tributario del Impuesto de Transmisiones Patrimoniales. "
        "Lleva el número '620', casillas de liquidación, importe del impuesto, "
        "datos de transmitente y adquirente. NO autoriza circulación."
    ),
    TipoDocumento.CTI: (
        "Certificado de características técnicas / tarjeta ITV. Contiene datos "
        "técnicos del vehículo: peso, dimensiones, emisiones, resultado de inspección."
    ),
    TipoDocumento.DNI: (
        "Documento Nacional de Identidad. Foto, nombre, número de DNI, fecha de nacimiento."
    ),
    TipoDocumento.CONTRATO_COMPRAVENTA: (
        "Contrato privado de compraventa del vehículo entre dos partes. "
        "Datos de comprador, vendedor, vehículo, precio, firmas."
    ),
    TipoDocumento.FICHA_TECNICA: (
        "Ficha técnica del fabricante con especificaciones del vehículo."
    ),
    TipoDocumento.JUSTIFICANTE_PAGO: (
        "Comprobante de pago de tasa o impuesto. Importe, fecha, referencia bancaria."
    ),
    TipoDocumento.CERTIFICADO_DEFUNCION: (
        "Certificado de defunción del Registro Civil. Requerido en herencias."
    ),
    TipoDocumento.MANDATO_REPRESENTACION: (
        "Autorización del titular para que la gestoría actúe en su nombre."
    ),
    TipoDocumento.RELACION_TRANSMISIONES: (
        "Formulario duplicado de la gestoría que lista todas las transferencias "
        "enviadas en el lote. Se cruza con el listado de Tempus."
    ),
    TipoDocumento.RELACION_MATRICULACIONES: (
        "Formulario duplicado de la gestoría que lista las matriculaciones del lote."
    ),
    TipoDocumento.HOJA_CAJA: (
        "Listado diario de la gestoría con los trámites realizados, para facturación en SAGE."
    ),
    TipoDocumento.SOLICITUD_MATRICULACION: (
        "Impreso oficial DGT para solicitar la matriculación de un vehículo."
    ),
    TipoDocumento.IVTM: (
        "Impuesto sobre Vehículos de Tracción Mecánica. Justificante de liquidación municipal."
    ),
    TipoDocumento.IMPUESTO_MATRICULACION: (
        "Impuesto Especial sobre Determinados Medios de Transporte (matriculación). "
        "Exento para remolques y semirremolques."
    ),
    TipoDocumento.DOCUMENTACION_EXTRANJERA: (
        "Certificado de conformidad UE o declaración de importación. "
        "Requerida para vehículos procedentes de UE o países terceros."
    ),
    TipoDocumento.MODELO_650: (
        "Impuesto de Sucesiones y Donaciones. Requerido en transferencias por herencia."
    ),
    TipoDocumento.DECLARACION_HEREDEROS: (
        "Acta notarial de declaración de herederos o testamento. Requerida en herencias."
    ),
    TipoDocumento.ANEXO_650: (
        "Relación de bienes hereditarios adjunta al modelo 650. "
        "El vehículo debe figurar por su bastidor."
    ),
    TipoDocumento.ESCRITURA_PODER: (
        "Escritura notarial de poder de representación. "
        "Requerida cuando el adquirente o transmitente es persona jurídica."
    ),
    TipoDocumento.CIF: (
        "Certificado de Identificación Fiscal de persona jurídica."
    ),
    TipoDocumento.SOLICITUD_BAJA: (
        "Modelo 05-B DGT para solicitar la baja del vehículo."
    ),
    TipoDocumento.SOLICITUD_DUPLICADO: (
        "Modelo 05-A DGT para solicitar duplicado de permiso o ficha técnica."
    ),
    TipoDocumento.JUSTIFICANTE_DOMICILIO: (
        "Certificado de empadronamiento o factura de suministro del domicilio actual."
    ),
    TipoDocumento.CARTILLA_AGRICOLA: (
        "Registro oficial de maquinaria agrícola. Requerida para tractores y aperos."
    ),
    TipoDocumento.CERTIFICADO_HOMOLOGACION_ELECTRICO: (
        "Certificado de homologación de vehículo eléctrico para placas verdes."
    ),
}

# Inicializar aquí, después de que TipoDocumento esté completamente definido
CAMPOS_REQUERIDOS.update(_init_campos_requeridos())
