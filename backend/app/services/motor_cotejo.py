"""
Motor de cotejo documental de Tyrion — SEGUNDO MÓDULO.

Toma un documento ya clasificado (capa 3: DETECTADO) y decide su validez
respecto a un requisito concreto de un trámite (capa 4: VÁLIDO).

La validez vive en el VÍNCULO documento-trámite, nunca en el documento:
  - VALIDO              → desbloquea ESE requisito de ESE trámite
  - EVIDENCIA_COMPATIBLE → relacionado pero no desbloquea (regla de oro)
  - RECHAZADO           → no sirve para este trámite
  - NO_APLICA           → el documento no está asociado a este requisito

Principio de escalado (documentado en estudio-ia):
  1. Tyrion prepara mensaje a la gestoría y espera.
  2. Solo si la gestoría no resuelve (o la situación es irresolvable por Tyrion)
     se escala al administrativo. El admin es el último recurso, no el primero.

resolver_checklist() implementa el árbol de decisión de docs/matriz-documental-tramites.md §5.
La función es pura y determinista; la tabla `requisitos_tramite` en BD la sustituirá en v2.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import (
    CHECKLIST_POR_TRAMITE,
    CONFUSIONES_FRECUENTES,
    FamiliaTramite,
    NaturalezaPartes,
    OrigenVehiculo,
    SubtipoTramite,
    TipoDocumento,
    TipoTramite,
    TipoVehiculo,
    ValidezVinculo,
)

logger = logging.getLogger(__name__)


@dataclass
class RequisitoCotejo:
    """Un requisito del checklist de un trámite."""
    requisito: str          # clave canónica, e.g. 'permiso_circulacion'
    descripcion: str = ""
    obligatorio: bool = True


@dataclass
class ResultadoCotejo:
    """Resultado de cotejar un documento clasificado contra un requisito."""
    requisito: str
    tipo_tramite: TipoTramite
    validez: ValidezVinculo
    motivo: str
    # True solo si Tyrion no puede resolver sin intervención del administrativo
    requiere_escalado_admin: bool = False


@dataclass
class EstadoChecklist:
    """Estado del checklist completo de un trámite tras cotejar los documentos."""
    tipo_tramite: TipoTramite
    requisitos_validos: list[str] = field(default_factory=list)
    requisitos_faltantes: list[str] = field(default_factory=list)
    requisitos_evidencia: list[str] = field(default_factory=list)   # compatible ≠ válido
    requisitos_rechazados: list[str] = field(default_factory=list)
    verificaciones: list[dict] = field(default_factory=list)

    @property
    def verificaciones_fallidas(self) -> list[dict]:
        return [
            v for v in self.verificaciones
            if v.get("estado") == "discrepancia" and v.get("criticidad") == "CRITICA"
        ]

    @property
    def completo(self) -> bool:
        """True cuando todos los requisitos obligatorios están cubiertos como VALIDO."""
        return (
            not self.requisitos_faltantes
            and not self.requisitos_evidencia
            and not self.requisitos_rechazados
            and not self.verificaciones_fallidas
        )

    @property
    def debe_pedir_gestoria(self) -> bool:
        """Hay documentos faltantes, insuficientes o incorrectos: pedir a gestoría primero.
        Los rechazados también van a gestoría (T+0): se les pide el documento correcto.
        El escalado al admin solo ocurre si la gestoría no responde (T+60 via timers)."""
        return bool(
            self.requisitos_faltantes
            or self.requisitos_evidencia
            or self.requisitos_rechazados
            or self.verificaciones_fallidas
        )

    @property
    def debe_escalar_admin(self) -> bool:
        """Escalar al administrativo solo si hay documentos explícitamente rechazados
        y no pueden resolverse pidiendo a la gestoría (último recurso)."""
        return bool(self.requisitos_rechazados)


# Tipos emparentados que pueden ser "evidencia compatible" aunque no validan.
# Simétrico: si A confunde con B, B también es compatible con A.
def _construir_mapa_compatibles() -> dict[str, set[str]]:
    mapa: dict[str, set[str]] = {}
    for tipo, confusiones in CONFUSIONES_FRECUENTES.items():
        clave = tipo.value
        mapa.setdefault(clave, set()).update(c.value for c in confusiones)
        for confundido in confusiones:
            mapa.setdefault(confundido.value, set()).add(clave)
    return mapa


_MAPA_COMPATIBLES: dict[str, set[str]] = _construir_mapa_compatibles()


@dataclass
class ChecklistResuelto:
    """Resultado de resolver_checklist(): requisitos aplicables + banderas de proceso."""
    requisitos: list[str]
    flags: dict[str, Any] = field(default_factory=dict)

    # Accesos rápidos a banderas comunes
    @property
    def no_telematico(self) -> bool:
        return bool(self.flags.get("no_telematico"))

    @property
    def requiere_revision_manual(self) -> bool:
        return bool(self.flags.get("requiere_revision_manual"))


def resolver_checklist(
    familia: FamiliaTramite,
    subtipo: SubtipoTramite = SubtipoTramite.NINGUNO,
    origen: OrigenVehiculo = OrigenVehiculo.ESPANA,
    tipo_vehiculo: TipoVehiculo = TipoVehiculo.TURISMO,
    naturaleza_partes: NaturalezaPartes = NaturalezaPartes.PARTICULAR,
) -> ChecklistResuelto:
    """Árbol de decisión parametrizado para los requisitos de un trámite.

    Implementa la matriz docs/matriz-documental-tramites.md §5.
    Devuelve la lista exacta de requisitos obligatorios para la combinación
    de parámetros dada, más banderas de proceso (no_telematico, etc.).

    Es pura y determinista: no toca BD, no tiene efectos secundarios.
    """
    flags: dict[str, Any] = {}

    # ── Checklist base por familia ─────────────────────────────────────────────
    if familia == FamiliaTramite.TRANSFERENCIA:
        # Versión acotada vigente: CTI + modelo_620 únicamente.
        # Sin DNI ni contrato_compraventa (versión acotada permitida temporalmente).
        # Previsto ampliar en próximos meses — actualizar cuando Colegio confirme.
        base = ["cti", "modelo_620"]

        if subtipo == SubtipoTramite.HERENCIA:
            # Herencia: cotejo real confirmado por administrativo (sesión 13).
            # Doc central: declaracion_responsable_fallecimiento (nombre, DNI, matrícula, firma).
            # Coteja contra: modelo_650 + anexo_650.
            # certificado_defuncion: condicional vía Tempus — Tyrion lo reconoce si llega,
            # pero NO lo solicita (lo gestiona Tempus directamente con la gestoría).
            # CTI = carátula del expediente físico, llega aparte, NO es doc de cotejo aquí.
            base = [
                "declaracion_responsable_fallecimiento",
                "modelo_650",
                "anexo_650",
            ]
        elif subtipo == SubtipoTramite.COMPRA_EMPRESA:
            naturaleza_partes = NaturalezaPartes.EMPRESA_ADQUIRENTE

    elif familia == FamiliaTramite.MATRICULACION:
        base = ["solicitud_matriculacion", "ficha_tecnica", "ivtm", "impuesto_matriculacion", "dni"]

        # §5.1.A — Remolque exento de impuesto de matriculación
        if tipo_vehiculo == TipoVehiculo.REMOLQUE:
            base.remove("impuesto_matriculacion")

        # §5.1.D — Documentación extranjera solo para vehículo usado de origen no español
        if subtipo == SubtipoTramite.USADO and origen in (OrigenVehiculo.UE, OrigenVehiculo.FUERA_UE):
            base.append("documentacion_extranjera")

    elif familia == FamiliaTramite.BAJA:
        base = ["permiso_circulacion", "dni", "solicitud_baja"]

    elif familia == FamiliaTramite.CAMBIO_DOMICILIO:
        base = ["permiso_circulacion", "dni", "justificante_domicilio"]

    elif familia in (FamiliaTramite.DUPLICADO_CIRCULACION, FamiliaTramite.DUPLICADO_FICHA):
        base = ["dni", "solicitud_duplicado", "justificante_pago"]

    elif familia == FamiliaTramite.CONDUCTORES:
        base = ["permiso_circulacion", "dni"]

    elif familia == FamiliaTramite.PLACAS_VERDES:
        base = ["permiso_circulacion", "ficha_tecnica", "certificado_homologacion_electrico"]

    elif familia == FamiliaTramite.PLACAS_ROJAS:
        base = ["dni", "justificante_pago"]

    else:
        base = []

    # ── Modificadores transversales ────────────────────────────────────────────

    # §5.1.B — Agrícola: requiere cartilla (se aplica a cualquier familia)
    if tipo_vehiculo == TipoVehiculo.AGRICOLA:
        base.append("cartilla_agricola")

    # §5.1.C — Histórico: no altera documentos, activa flag (ART.11 RD982/2024)
    if tipo_vehiculo == TipoVehiculo.HISTORICO:
        flags["no_telematico"] = True

    # §5.1.F — Empresa adquirente: escritura de poder + CIF
    if naturaleza_partes == NaturalezaPartes.EMPRESA_ADQUIRENTE:
        base += ["escritura_poder", "cif"]

    return ChecklistResuelto(requisitos=base, flags=flags)


_FAMILIA_DESDE_TIPO: dict[TipoTramite, str] = {
    TipoTramite.TRANSFERENCIA: "TRANSFERENCIA",
    TipoTramite.MATRICULACION: "MATRICULACION",
    TipoTramite.BAJA: "BAJA",
}


class MotorCotejo:
    """Coteja documentos clasificados contra el checklist del trámite.

    No tiene estado propio: es puro y determinista dado el clasificador.
    Se inyectan los requisitos para poder testear sin base de datos.
    """

    def cotejar_documento(
        self,
        clasificacion: ResultadoClasificacion,
        tipo_tramite: TipoTramite,
        requisito: str,
    ) -> ResultadoCotejo:
        """Decide la validez de un documento respecto a un requisito concreto.

        Reglas (en orden de prioridad):
          1. Tipo detectado == requisito Y confianza ALTA/MEDIA → VALIDO
          2. Tipo detectado == requisito Y confianza BAJA → EVIDENCIA_COMPATIBLE
             (Tyrion cree que es el documento correcto pero con poca certeza)
          3. Tipo detectado es un tipo confundido frecuentemente con el requisito
             → EVIDENCIA_COMPATIBLE (documento relacionado pero no el requerido)
          4. Cualquier otro caso → RECHAZADO
        """
        tipo_doc = clasificacion.tipo_detectado.value
        nivel = clasificacion.confianza_nivel

        # Regla 1: coincidencia exacta con confianza suficiente
        if tipo_doc == requisito and nivel in ("ALTA", "MEDIA"):
            return ResultadoCotejo(
                requisito=requisito,
                tipo_tramite=tipo_tramite,
                validez=ValidezVinculo.VALIDO,
                motivo=f"Tipo '{tipo_doc}' coincide con el requisito (confianza {nivel}).",
            )

        # Regla 2: coincidencia exacta pero confianza BAJA
        if tipo_doc == requisito and nivel == "BAJA":
            return ResultadoCotejo(
                requisito=requisito,
                tipo_tramite=tipo_tramite,
                validez=ValidezVinculo.EVIDENCIA_COMPATIBLE,
                motivo=(
                    f"El documento parece ser '{tipo_doc}' pero la confianza es BAJA "
                    f"({clasificacion.confianza_score:.2f}). "
                    "Se pedirá confirmación a la gestoría."
                ),
            )

        # Regla 3: tipo relacionado/confundido frecuentemente
        compatibles_del_requisito = _MAPA_COMPATIBLES.get(requisito, set())
        if tipo_doc in compatibles_del_requisito:
            return ResultadoCotejo(
                requisito=requisito,
                tipo_tramite=tipo_tramite,
                validez=ValidezVinculo.EVIDENCIA_COMPATIBLE,
                motivo=(
                    f"Se recibió '{tipo_doc}' pero el requisito es '{requisito}'. "
                    "Son documentos relacionados pero no intercambiables (regla de oro). "
                    "Se pedirá el documento correcto a la gestoría."
                ),
            )

        # Regla 4: rechazado
        return ResultadoCotejo(
            requisito=requisito,
            tipo_tramite=tipo_tramite,
            validez=ValidezVinculo.RECHAZADO,
            motivo=(
                f"El documento '{tipo_doc}' no corresponde al requisito '{requisito}' "
                f"ni es un tipo relacionado conocido."
            ),
            # Rechazo explícito sin tipo relacionado: el admin debe revisarlo
            requiere_escalado_admin=True,
        )

    def evaluar_checklist(
        self,
        tipo_tramite: TipoTramite,
        documentos_por_requisito: dict[str, ResultadoClasificacion],
        requisitos: list[RequisitoCotejo] | None = None,
        familia: str = "",
        subtipo: str = "ninguno",
    ) -> EstadoChecklist:
        """Evalúa el checklist completo de un trámite.

        Args:
            tipo_tramite: tipo del trámite (TRANSFERENCIA, MATRICULACION, BAJA).
            documentos_por_requisito: mapa {requisito: clasificacion} con los
                documentos que la gestoría ya envió para cada requisito.
                Un requisito ausente del mapa = documento no recibido todavía.
            requisitos: lista de requisitos del checklist. Si es None, usa el
                checklist por defecto de CHECKLIST_POR_TRAMITE.

        Returns:
            EstadoChecklist con el resumen y las listas de acción.
        """
        if requisitos is None:
            requisitos = [
                RequisitoCotejo(requisito=r)
                for r in CHECKLIST_POR_TRAMITE.get(tipo_tramite, [])
            ]

        estado = EstadoChecklist(tipo_tramite=tipo_tramite)

        for req in requisitos:
            if not req.obligatorio:
                continue

            clasificacion = documentos_por_requisito.get(req.requisito)

            if clasificacion is None:
                # Documento no recibido → pedir a gestoría
                estado.requisitos_faltantes.append(req.requisito)
                logger.debug("Trámite %s: falta '%s'", tipo_tramite.value, req.requisito)
                continue

            resultado = self.cotejar_documento(clasificacion, tipo_tramite, req.requisito)

            if resultado.validez == ValidezVinculo.VALIDO:
                estado.requisitos_validos.append(req.requisito)

            elif resultado.validez == ValidezVinculo.EVIDENCIA_COMPATIBLE:
                estado.requisitos_evidencia.append(req.requisito)
                logger.info(
                    "Trámite %s, requisito '%s': evidencia compatible — %s",
                    tipo_tramite.value, req.requisito, resultado.motivo,
                )

            elif resultado.validez == ValidezVinculo.RECHAZADO:
                estado.requisitos_rechazados.append(req.requisito)
                logger.warning(
                    "Trámite %s, requisito '%s': RECHAZADO — %s",
                    tipo_tramite.value, req.requisito, resultado.motivo,
                )

        # Tras el bucle — cruce de datos entre documentos
        from app.services.motor_cruce import cotejar_datos
        docs_por_tipo: dict[str, dict] = {}
        for tipo_req, clf in documentos_por_requisito.items():
            if hasattr(clf, "datos_extraidos"):
                docs_por_tipo[tipo_req] = clf.datos_extraidos or {}
            elif isinstance(clf, dict):
                docs_por_tipo[tipo_req] = clf
        fam = familia or _FAMILIA_DESDE_TIPO.get(tipo_tramite, "")
        if fam:
            estado.verificaciones = cotejar_datos(fam, subtipo, docs_por_tipo)

        return estado

    def preparar_mensaje_gestoria(
        self,
        estado: EstadoChecklist,
        matricula: str | None = None,
    ) -> str:
        """Redacta el cuerpo del mensaje a la gestoría para solicitar documentos.

        Tyrion siempre pide a la gestoría antes de escalar al administrativo.
        """
        if not estado.debe_pedir_gestoria:
            return ""

        lineas = [
            f"Estimada gestoría,",
            "",
            f"Revisamos el expediente"
            + (f" del vehículo {matricula}" if matricula else "")
            + f" para el trámite de {estado.tipo_tramite.value}.",
            "",
        ]

        if estado.requisitos_faltantes:
            lineas.append("Documentos pendientes de recibir:")
            for req in estado.requisitos_faltantes:
                lineas.append(f"  • {req}")
            lineas.append("")

        if estado.requisitos_evidencia:
            lineas.append(
                "Documentos recibidos pero que requieren aclaración o reenvío:"
            )
            for req in estado.requisitos_evidencia:
                lineas.append(f"  • {req}")
            lineas.append("")

        if estado.requisitos_rechazados:
            lineas.append("Documentos incorrectos que deben ser reemplazados:")
            for req in estado.requisitos_rechazados:
                lineas.append(f"  • {req}")
            lineas.append("")

        lineas += [
            "Rogamos envíen la documentación a la mayor brevedad para poder",
            "completar el expediente.",
            "",
            "Gracias,",
            "Colegio de Gestores",
        ]

        return "\n".join(lineas)
