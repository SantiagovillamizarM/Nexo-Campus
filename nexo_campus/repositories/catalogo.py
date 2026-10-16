"""Consultas del catálogo (espacios, recursos, incidencias y reporte de calidad) y registro de espacios y recursos."""

from sqlalchemy import Engine
from sqlmodel import select

from nexo_campus import db
from nexo_campus.models import Espacio, Incidencia, Recurso, RegistroInconsistente, TipoInconsistencia


def listar_espacios(motor_db: Engine = db.motor) -> list[Espacio]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Espacio).order_by(Espacio.id)))


def listar_recursos(motor_db: Engine = db.motor) -> list[Recurso]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Recurso).order_by(Recurso.id)))


def listar_incidencias(motor_db: Engine = db.motor) -> list[Incidencia]:
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(select(Incidencia).order_by(Incidencia.id)))


def guardar_espacio(espacio: Espacio, motor_db: Engine = db.motor) -> Espacio:
    """Crea el espacio si su código no existe; si ya existe, lo actualiza."""
    with db.obtener_sesion(motor_db) as sesion:
        guardado = sesion.merge(espacio)
        sesion.commit()
        sesion.refresh(guardado)
        return guardado


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
