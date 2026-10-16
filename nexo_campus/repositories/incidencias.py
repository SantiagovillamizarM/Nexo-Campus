"""Consultas y escrituras de incidencias. Lo usan services/incidencias.py (P3) y la regla central (P2).

Una incidencia está abierta mientras no esté cerrada (incluye las que están en proceso).
"""

from datetime import datetime

from sqlalchemy import Engine
from sqlmodel import select

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import EstadoIncidencia, Incidencia, Prioridad


def guardar_incidencia(incidencia: Incidencia, motor_db: Engine = db.motor) -> Incidencia:
    """Crea la incidencia si no tiene id; si ya lo tiene, actualiza la existente. Devuelve la incidencia guardada."""
    with db.obtener_sesion(motor_db) as sesion:
        guardada = sesion.merge(incidencia)
        sesion.commit()
        sesion.refresh(guardada)
        return guardada


def obtener_incidencia(incidencia_id: int, motor_db: Engine = db.motor) -> Incidencia | None:
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.get(Incidencia, incidencia_id)


def listar_incidencias(
    estado: EstadoIncidencia | None = None,
    prioridad: Prioridad | None = None,
    motor_db: Engine = db.motor,
) -> list[Incidencia]:
    """Las más recientes primero."""
    consulta = select(Incidencia).order_by(Incidencia.id.desc())
    if estado is not None:
        consulta = consulta.where(Incidencia.estado == estado)
    if prioridad is not None:
        consulta = consulta.where(Incidencia.prioridad == prioridad)
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def cerrar_incidencia(incidencia_id: int, motor_db: Engine = db.motor) -> Incidencia:
    """Pasa la incidencia a cerrada y pone la fecha de cierre."""
    with db.obtener_sesion(motor_db) as sesion:
        incidencia = sesion.get(Incidencia, incidencia_id)
        if incidencia is None:
            raise ReglaNegocioError(f"No existe la incidencia #{incidencia_id}.")
        incidencia.estado = EstadoIncidencia.cerrada
        incidencia.fecha_cierre = datetime.now()
        sesion.commit()
        sesion.refresh(incidencia)
        return incidencia


def incidencias_abiertas_de(
    espacio_id: str | None = None, recurso_id: str | None = None, motor_db: Engine = db.motor
) -> list[Incidencia]:
    """Incidencias no cerradas del espacio y/o recurso indicados. Sin filtros, todas las abiertas."""
    consulta = select(Incidencia).where(Incidencia.estado != EstadoIncidencia.cerrada).order_by(Incidencia.id)
    if espacio_id is not None:
        consulta = consulta.where(Incidencia.espacio_id == espacio_id)
    if recurso_id is not None:
        consulta = consulta.where(Incidencia.recurso_id == recurso_id)
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))
