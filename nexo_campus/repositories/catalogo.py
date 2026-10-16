"""Consultas del catálogo (espacios, recursos, incidencias y reporte de calidad) y registro de espacios y recursos."""

from sqlalchemy import Engine
from sqlmodel import select

from nexo_campus import db
from nexo_campus.carga.normalizacion import normalizar_clave
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import (
    Espacio,
    EstadoEspacio,
    HistorialEstadoEspacio,
    Incidencia,
    OrigenCambioEstado,
    Recurso,
    RegistroInconsistente,
    TipoInconsistencia,
)


def listar_espacios(motor_db: Engine = db.motor) -> list[Espacio]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Espacio).order_by(Espacio.id)))


def listar_recursos(motor_db: Engine = db.motor) -> list[Recurso]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Recurso).order_by(Recurso.id)))


def listar_incidencias(motor_db: Engine = db.motor) -> list[Incidencia]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Incidencia).order_by(Incidencia.id)))


def recursos_en_espacio(espacio: Espacio, motor_db: Engine = db.motor) -> list[Recurso]:
    """Equipos ubicados en el espacio (por su ubicación: 'Apolo' coincide con el espacio APOLO / Apolo)."""
    claves = {normalizar_clave(espacio.id), normalizar_clave(espacio.nombre)}
    with db.obtener_sesion(motor_db) as sesion:
        recursos = sesion.exec(select(Recurso).where(Recurso.ubicacion.is_not(None)).order_by(Recurso.id))
        return [r for r in recursos if normalizar_clave(r.ubicacion) in claves]


def guardar_espacio(espacio: Espacio, motor_db: Engine = db.motor) -> Espacio:
    """Crea el espacio si su código no existe; si ya existe, lo actualiza."""
    with db.obtener_sesion(motor_db) as sesion:
        guardado = sesion.merge(espacio)
        sesion.commit()
        sesion.refresh(guardado)
        return guardado


def cambiar_estado_espacio(
    espacio_id: str,
    nuevo_estado: EstadoEspacio,
    motivo: str | None,
    origen: OrigenCambioEstado,
    motor_db: Engine = db.motor,
) -> Espacio:
    """Cambia el estado del espacio y escribe el historial en la misma transacción. Si no cambia, no escribe nada."""
    with db.obtener_sesion(motor_db) as sesion:
        espacio = sesion.get(Espacio, espacio_id)
        if espacio is None:
            raise ReglaNegocioError(f"No existe un espacio con el código '{espacio_id}'.")
        if espacio.estado is nuevo_estado:
            return espacio
        sesion.add(
            HistorialEstadoEspacio(
                espacio_id=espacio_id, estado_anterior=espacio.estado, estado_nuevo=nuevo_estado,
                motivo=motivo, origen=origen,
            )
        )
        espacio.estado = nuevo_estado
        sesion.commit()
        sesion.refresh(espacio)
        return espacio


def listar_historial_espacio(espacio_id: str, motor_db: Engine = db.motor) -> list[HistorialEstadoEspacio]:
    """Del cambio más reciente al más antiguo."""
    consulta = (
        select(HistorialEstadoEspacio)
        .where(HistorialEstadoEspacio.espacio_id == espacio_id)
        .order_by(HistorialEstadoEspacio.fecha.desc(), HistorialEstadoEspacio.id.desc())
    )
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def guardar_recurso(recurso: Recurso, motor_db: Engine = db.motor) -> Recurso:
    """Crea el recurso si su código no existe; si ya existe, lo actualiza (el estado se cambia aparte, con historial)."""
    with db.obtener_sesion(motor_db) as sesion:
        guardado = sesion.merge(recurso)
        sesion.commit()
        sesion.refresh(guardado)
        return guardado


def listar_inconsistencias(
    tipo: TipoInconsistencia | None = None, motor_db: Engine = db.motor
) -> list[RegistroInconsistente]:
    with db.obtener_sesion(motor_db) as sesion:
        consulta = select(RegistroInconsistente).order_by(RegistroInconsistente.entidad, RegistroInconsistente.fila)
        if tipo is not None:
            consulta = consulta.where(RegistroInconsistente.tipo == tipo)
        return list(sesion.exec(consulta))
