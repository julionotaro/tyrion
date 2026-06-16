"""
Tests del motor de cotejo documental.

Sin llamadas a la API ni base de datos: todo es puro y determinista.
Verifican las cuatro reglas de validez y el principio de escalado:
  Tyrion pide a la gestoría primero; escala al admin solo como último recurso.
"""
import pytest

from app.schemas.clasificacion import ResultadoClasificacion
from app.services.catalogo_documental import (
    TipoDocumento,
    TipoTramite,
    ValidezVinculo,
)
from app.services.motor_cotejo import (
    EstadoChecklist,
    MotorCotejo,
    RequisitoCotejo,
)


# ---------- helpers ----------

def _clasificacion(
    tipo: TipoDocumento,
    score: float,
) -> ResultadoClasificacion:
    if score >= 0.85:
        nivel = "ALTA"
    elif score >= 0.60:
        nivel = "MEDIA"
    else:
        nivel = "BAJA"
    return ResultadoClasificacion(
        tipo_detectado=tipo,
        confianza_score=score,
        confianza_nivel=nivel,
    )


@pytest.fixture
def motor() -> MotorCotejo:
    return MotorCotejo()


# ---------- Regla 1: VALIDO (coincidencia + confianza suficiente) ----------

def test_valido_con_confianza_alta(motor):
    clf = _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.VALIDO
    assert not res.requiere_escalado_admin


def test_valido_con_confianza_media(motor):
    clf = _clasificacion(TipoDocumento.MODELO_620, 0.72)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "modelo_620")

    assert res.validez == ValidezVinculo.VALIDO
    assert not res.requiere_escalado_admin


# ---------- Regla 2: EVIDENCIA_COMPATIBLE (coincidencia + confianza BAJA) ----------

def test_evidencia_compatible_por_confianza_baja(motor):
    """El tipo coincide pero con poca certeza: pedir confirmación a gestoría, no al admin."""
    clf = _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.45)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.EVIDENCIA_COMPATIBLE
    assert not res.requiere_escalado_admin   # gestoría primero, no admin


# ---------- Regla 3: EVIDENCIA_COMPATIBLE (tipo relacionado/confundido) ----------

def test_modelo_620_no_sustituye_permiso_circulacion(motor):
    """La regla de oro: evidencia compatible ≠ documento válido."""
    clf = _clasificacion(TipoDocumento.MODELO_620, 0.92)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.EVIDENCIA_COMPATIBLE
    assert not res.requiere_escalado_admin


def test_cti_no_sustituye_permiso_circulacion(motor):
    clf = _clasificacion(TipoDocumento.CTI, 0.88)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.EVIDENCIA_COMPATIBLE


def test_ficha_tecnica_compatible_con_cti(motor):
    """CTI y ficha técnica son confundidos frecuentemente: evidencia compatible."""
    clf = _clasificacion(TipoDocumento.FICHA_TECNICA, 0.90)
    res = motor.cotejar_documento(clf, TipoTramite.MATRICULACION, "cti")

    assert res.validez == ValidezVinculo.EVIDENCIA_COMPATIBLE


# ---------- Regla 4: RECHAZADO (documento no relacionado) ----------

def test_rechazado_documento_irrelevante(motor):
    """Un certificado de defunción no tiene relación con el permiso de circulación."""
    clf = _clasificacion(TipoDocumento.CERTIFICADO_DEFUNCION, 0.95)
    res = motor.cotejar_documento(clf, TipoTramite.TRANSFERENCIA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.RECHAZADO
    # Rechazo explícito → escalar al admin (último recurso)
    assert res.requiere_escalado_admin


def test_rechazado_escala_al_admin_no_gestoria(motor):
    """El escalado al admin ocurre solo en rechazos, nunca en faltantes."""
    clf = _clasificacion(TipoDocumento.HOJA_CAJA, 0.90)
    res = motor.cotejar_documento(clf, TipoTramite.BAJA, "permiso_circulacion")

    assert res.validez == ValidezVinculo.RECHAZADO
    assert res.requiere_escalado_admin


# ---------- evaluar_checklist: estado completo del trámite ----------

def test_checklist_completo_transferencia(motor):
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95),
        "modelo_620": _clasificacion(TipoDocumento.MODELO_620, 0.88),
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
        "contrato_compraventa": _clasificacion(TipoDocumento.CONTRATO_COMPRAVENTA, 0.85),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs)

    assert estado.completo
    assert len(estado.requisitos_validos) == 4
    assert not estado.requisitos_faltantes
    assert not estado.debe_pedir_gestoria
    assert not estado.debe_escalar_admin


def test_checklist_con_documento_faltante(motor):
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95),
        # modelo_620 falta
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
        "contrato_compraventa": _clasificacion(TipoDocumento.CONTRATO_COMPRAVENTA, 0.85),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs)

    assert not estado.completo
    assert "modelo_620" in estado.requisitos_faltantes
    # Tyrion pide a la gestoría, no al admin
    assert estado.debe_pedir_gestoria
    assert not estado.debe_escalar_admin


def test_checklist_con_evidencia_compatible(motor):
    """Se envió un CTI en lugar del permiso: evidencia compatible, pedir a gestoría."""
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.CTI, 0.90),
        "modelo_620": _clasificacion(TipoDocumento.MODELO_620, 0.88),
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
        "contrato_compraventa": _clasificacion(TipoDocumento.CONTRATO_COMPRAVENTA, 0.85),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs)

    assert not estado.completo
    assert "permiso_circulacion" in estado.requisitos_evidencia
    assert estado.debe_pedir_gestoria
    assert not estado.debe_escalar_admin   # gestoría primero


def test_checklist_con_documento_rechazado_escala_admin(motor):
    """Documento rechazado (sin relación) → escalar al admin como último recurso."""
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.HOJA_CAJA, 0.90),
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
    }
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs)

    assert not estado.completo
    assert "permiso_circulacion" in estado.requisitos_rechazados
    assert estado.debe_escalar_admin


# ---------- checklist con requisitos personalizados (sin BD) ----------

def test_checklist_con_requisitos_personalizados(motor):
    """El motor acepta una lista de requisitos inyectada (p.ej. desde BD)."""
    requisitos = [
        RequisitoCotejo(requisito="permiso_circulacion"),
        RequisitoCotejo(requisito="certificado_defuncion"),  # herencia
    ]
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.90),
        # certificado_defuncion no se recibió
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs, requisitos=requisitos)

    assert not estado.completo
    assert "certificado_defuncion" in estado.requisitos_faltantes


def test_requisito_no_obligatorio_no_bloquea(motor):
    """Los requisitos opcionales no bloquean el trámite si faltan."""
    requisitos = [
        RequisitoCotejo(requisito="permiso_circulacion", obligatorio=True),
        RequisitoCotejo(requisito="mandato_representacion", obligatorio=False),
    ]
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95),
        # mandato_representacion ausente pero opcional
    }
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs, requisitos=requisitos)

    assert estado.completo


# ---------- preparar_mensaje_gestoria ----------

def test_mensaje_gestoria_incluye_faltantes(motor):
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95),
    }
    estado = motor.evaluar_checklist(TipoTramite.TRANSFERENCIA, docs)
    mensaje = motor.preparar_mensaje_gestoria(estado, matricula="1234ABC")

    assert "1234ABC" in mensaje
    assert "modelo_620" in mensaje
    assert "dni" in mensaje
    assert "contrato_compraventa" in mensaje


def test_mensaje_gestoria_vacio_si_completo(motor):
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.PERMISO_CIRCULACION, 0.95),
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
    }
    requisitos = [
        RequisitoCotejo(requisito="permiso_circulacion"),
        RequisitoCotejo(requisito="dni"),
    ]
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs, requisitos=requisitos)
    assert motor.preparar_mensaje_gestoria(estado) == ""


def test_mensaje_menciona_evidencia_compatible(motor):
    docs = {
        "permiso_circulacion": _clasificacion(TipoDocumento.CTI, 0.88),
        "dni": _clasificacion(TipoDocumento.DNI, 0.92),
    }
    requisitos = [
        RequisitoCotejo(requisito="permiso_circulacion"),
        RequisitoCotejo(requisito="dni"),
    ]
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs, requisitos=requisitos)
    mensaje = motor.preparar_mensaje_gestoria(estado)

    assert "permiso_circulacion" in mensaje
    assert mensaje  # no vacío


# ---------- integración clasificador → motor (sin API) ----------

def test_pipeline_completo_baja_con_discrepancia(motor):
    """Simula el pipeline: la gestoría dice 'permiso' pero manda un CTI.
    Motor detecta evidencia compatible y prepara mensaje a gestoría (no admin)."""
    # CTI con confianza alta pero NO es el permiso_circulacion
    clf_cti = ResultadoClasificacion(
        tipo_detectado=TipoDocumento.CTI,
        confianza_score=0.91,
        confianza_nivel="ALTA",
        discrepancia_con_declarado=True,
        justificacion="Tarjeta ITV visible, no permiso de circulación.",
    )
    clf_dni = _clasificacion(TipoDocumento.DNI, 0.94)

    docs = {
        "permiso_circulacion": clf_cti,
        "dni": clf_dni,
    }
    estado = motor.evaluar_checklist(TipoTramite.BAJA, docs)

    assert not estado.completo
    assert "permiso_circulacion" in estado.requisitos_evidencia
    assert estado.debe_pedir_gestoria
    assert not estado.debe_escalar_admin

    mensaje = motor.preparar_mensaje_gestoria(estado, matricula="9999ZZZ")
    assert "9999ZZZ" in mensaje
    assert "permiso_circulacion" in mensaje
