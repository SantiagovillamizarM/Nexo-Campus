"""Consultas y escrituras de recursos, préstamos e historial de estados. Lo usa services/prestamos.py.

Aquí no se decide si un préstamo es válido (eso está en rules/prestamos.py): solo se busca y se guarda.
"""

from sqlalchemy import Engine, func
from sqlmodel import select

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import (
    EstadoPrestamo,
    EstadoRecurso,
    HistorialEstadoRecurso,
    OrigenCambioEstado,
    Prestamo,
    Recurso,
)


def obtener_recurso(recurso_id: str, motor_db: Engine = db.motor) -> Recurso | None:
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.get(Recurso, recurso_id)


def obtener_prestamo(prestamo_id: int, motor_db: Engine = db.motor) -> Prestamo | None:
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.get(Prestamo, prestamo_id)


def prestamo_activo_de_recurso(recurso_id: str, motor_db: Engine = db.motor) -> Prestamo | None:
    consulta = select(Prestamo).where(Prestamo.recurso_id == recurso_id, Prestamo.estado == EstadoPrestamo.activo)
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.exec(consulta).first()


def prestamos_activos_de(solicitante: str, motor_db: Engine = db.motor) -> list[Prestamo]:
    """Préstamos activos de una persona. No distingue mayúsculas ni espacios de más ("ana " es "Ana")."""
    nombre = " ".join(solicitante.split()).lower()
    consulta = (
        select(Prestamo)
        .where(Prestamo.estado == EstadoPrestamo.activo, func.lower(func.trim(Prestamo.solicitante)) == nombre)
        .order_by(Prestamo.fecha_prestamo)
    )
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def guardar_prestamo(prestamo: Prestamo, motor_db: Engine = db.motor) -> Prestamo:
    """Crea el préstamo si no tiene id; si ya lo tiene, actualiza el existente. Devuelve el préstamo guardado."""
    with db.obtener_sesion(motor_db) as sesion:
        guardado = sesion.merge(prestamo)
        sesion.commit()
        sesion.refresh(guardado)
        return guardado


def cambiar_estado_recurso(
    recurso_id: str,
    nuevo_estado: EstadoRecurso,
    motivo: str | None,
    origen: OrigenCambioEstado,
    motor_db: Engine = db.motor,
) -> Recurso:
    """Cambia el estado del recurso y escribe el historial en la misma transacción.

    Si el recurso ya está en ese estado no se escribe nada, para no llenar el historial de cambios vacíos.
    """
    with db.obtener_sesion(motor_db) as sesion:
        recurso = sesion.get(Recurso, recurso_id)
        if recurso is None:
            raise ReglaNegocioError(f"No existe un recurso con el código '{recurso_id}'.")
        if recurso.estado is nuevo_estado:
            return recurso
        sesion.add(
            HistorialEstadoRecurso(
                recurso_id=recurso_id,
                estado_anterior=recurso.estado,
                estado_nuevo=nuevo_estado,
                motivo=motivo,
                origen=origen,
            )
        )
        recurso.estado = nuevo_estado
        sesion.commit()
        sesion.refresh(recurso)
        return recurso


def listar_historial(recurso_id: str, motor_db: Engine = db.motor) -> list[HistorialEstadoRecurso]:
    """Del cambio más reciente al más antiguo."""
    consulta = (
        select(HistorialEstadoRecurso)
        .where(HistorialEstadoRecurso.recurso_id == recurso_id)
        .order_by(HistorialEstadoRecurso.fecha.desc(), HistorialEstadoRecurso.id.desc())
    )
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def listar_prestamos(activos: bool | None = None, motor_db: Engine = db.motor) -> list[Prestamo]:
    """Todos los préstamos (None), solo los activos (True) o solo los devueltos (False). Los más recientes primero."""
    consulta = select(Prestamo).order_by(Prestamo.fecha_prestamo.desc(), Prestamo.id.desc())
    if activos is not None:
        estado = EstadoPrestamo.activo if activos else EstadoPrestamo.devuelto
        consulta = consulta.where(Prestamo.estado == estado)
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))
