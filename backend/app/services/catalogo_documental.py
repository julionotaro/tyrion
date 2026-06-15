"""
Catálogo del dominio de trámites de vehículos ante DGT.

Incluye:
  - TipoDocumento: tipos documentales que Tyrion reconoce.
  - TipoTramite / ValidezVinculo: enums del dominio (espejan los tipos SQL).
  - CHECKLIST_POR_TRAMITE: requisitos obligatorios por tipo (usados por el motor de cotejo
    cuando no hay datos de base de datos disponibles, p.ej. en tests).

Catálogo de tipos documentales del dominio de trámites de vehículos ante DGT.

Fuente: Reglamentación general de vehículos título IV + vocabulario de la oficina
(entrevista sesión 1). Este catálogo alimenta al clasificador: define qué tipos
puede detectar Tyrion y cuáles son comúnmente confundidos por las gestorías.

NOTA: la lista de requisitos por tipo de trámite vive en la tabla
`requisitos_tramite` (editable sin redeploy). Este módulo solo define el
vocabulario de TIPOS DE DOCUMENTO que el clasificador reconoce.
"""
from enum import Enum


class TipoDocumento(str, Enum):
    """Tipos documentales reconocidos. El valor es el identificador canónico."""

    PERMISO_CIRCULACION = "permiso_circulacion"
    MODELO_620 = "modelo_620"           # Impuesto de Transmisiones Patrimoniales
    CTI = "cti"                          # Certificado de Características Técnicas / ITV
    DNI = "dni"
    CONTRATO_COMPRAVENTA = "contrato_compraventa"
    FICHA_TECNICA = "ficha_tecnica"
    JUSTIFICANTE_PAGO = "justificante_pago"
    CERTIFICADO_DEFUNCION = "certificado_defuncion"   # herencias
    MANDATO_REPRESENTACION = "mandato_representacion"
    RELACION_TRANSMISIONES = "relacion_transmisiones" # formulario de la gestoría
    RELACION_MATRICULACIONES = "relacion_matriculaciones"
    HOJA_CAJA = "hoja_caja"             # para SAGE
    DESCONOCIDO = "desconocido"


# Confusiones comunes documentadas en la entrevista (B3.2).
# El cliente dice "Permiso" pero envía un 620, etc. El clasificador debe
# distinguirlos a pesar de lo que el remitente DECLARE (el tipo declarado
# es también una detección, no un dato confiable).
CONFUSIONES_FRECUENTES = {
    TipoDocumento.PERMISO_CIRCULACION: [TipoDocumento.MODELO_620, TipoDocumento.CTI],
    TipoDocumento.MODELO_620: [TipoDocumento.PERMISO_CIRCULACION, TipoDocumento.JUSTIFICANTE_PAGO],
    TipoDocumento.CTI: [TipoDocumento.FICHA_TECNICA, TipoDocumento.PERMISO_CIRCULACION],
}


# Descripciones para el prompt del clasificador: qué distingue a cada documento
# a simple vista (vocabulario real de la oficina).
class TipoTramite(str, Enum):
    """Tipos de trámite. Espeja el enum SQL `tipo_tramite`."""
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


# Checklist mínimo por tipo de trámite (fuente: entrevista sesión 1).
# La tabla `requisitos_tramite` en BD es la fuente viva; este diccionario
# sirve de fallback y para tests sin BD.
CHECKLIST_POR_TRAMITE: dict[TipoTramite, list[str]] = {
    TipoTramite.TRANSFERENCIA: [
        "permiso_circulacion",
        "modelo_620",
        "dni",
        "contrato_compraventa",
    ],
    TipoTramite.MATRICULACION: [
        "permiso_circulacion",
        "ficha_tecnica",
        "justificante_pago",
        "dni",
    ],
    TipoTramite.BAJA: [
        "permiso_circulacion",
        "dni",
    ],
}


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
}
