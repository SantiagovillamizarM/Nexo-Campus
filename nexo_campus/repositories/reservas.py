"""Consultas y escrituras de reservas en SQLite. Lo usa services/reservas.py.

Aquí no se decide si una reserva es válida (eso está en rules/reservas.py): solo se busca y se guarda.
Dos franjas se cruzan si cada una empieza antes de que termine la otra (08-10 y 10-12 no se cruzan).
"""

from datetime import datetime

from sqlalchemy import Engine
from sqlmodel import select

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoReserva, Reserva
from nexo_campus.rules.reservas import ESTADOS_RESERVABLES


def obtener_espacio(espacio_id: str, motor_db: Engine = db.motor) -> Espacio | None:
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.get(Espacio, espacio_id)


def obtener_reserva(reserva_id: int, motor_db: Engine = db.motor) -> Reserva | None:
    with db.obtener_sesion(motor_db) as sesion:
        return sesion.get(Reserva, reserva_id)


def listar_reservas(
    espacio_id: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    motor_db: Engine = db.motor,
) -> list[Reserva]:
    """Todas las reservas (activas y canceladas). desde/hasta devuelven las que se cruzan con ese rango."""
    consulta = select(Reserva).order_by(Reserva.inicio, Reserva.id)
    if espacio_id is not None:
        consulta = consulta.where(Reserva.espacio_id == espacio_id)
    if desde is not None:
        consulta = consulta.where(Reserva.fin > desde)
    if hasta is not None:
        consulta = consulta.where(Reserva.inicio < hasta)
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def _activas_que_se_cruzan(inicio: datetime, fin: datetime):
    return select(Reserva).where(
        Reserva.estado == EstadoReserva.activa,
        Reserva.inicio < fin,
        Reserva.fin > inicio,
    )


def reservas_activas_en_franja(
    espacio_id: str,
    inicio: datetime,
    fin: datetime,
    excluir_id: int | None = None,
    motor_db: Engine = db.motor,
) -> list[Reserva]:
    """Reservas activas del espacio que se cruzan con la franja. excluir_id evita que una reserva choque consigo misma."""
    consulta = _activas_que_se_cruzan(inicio, fin).where(Reserva.espacio_id == espacio_id).order_by(Reserva.inicio)
    if excluir_id is not None:
        consulta = consulta.where(Reserva.id != excluir_id)
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))


def guardar_reserva(reserva: Reserva, motor_db: Engine = db.motor) -> Reserva:
    """Crea la reserva si no tiene id; si ya lo tiene, actualiza la existente. Devuelve la reserva guardada."""
    with db.obtener_sesion(motor_db) as sesion:
        guardada = sesion.merge(reserva)
        sesion.commit()
        sesion.refresh(guardada)
        return guardada


def cancelar_reserva(reserva_id: int, motor_db: Engine = db.motor) -> Reserva:
    with db.obtener_sesion(motor_db) as sesion:
        reserva = sesion.get(Reserva, reserva_id)
        if reserva is None:
            raise ReglaNegocioError(f"No existe la reserva #{reserva_id}.")
        reserva.estado = EstadoReserva.cancelada
        sesion.commit()
        sesion.refresh(reserva)
        return reserva


def espacios_disponibles(
    inicio: datetime, fin: datetime, asistentes: int, motor_db: Engine = db.motor
) -> list[Espacio]:
    """Espacios habilitados, con aforo suficiente y sin reservas activas en la franja. Los más ajustados primero."""
    ocupados = _activas_que_se_cruzan(inicio, fin).with_only_columns(Reserva.espacio_id)
    consulta = (
        select(Espacio)
        .where(
            Espacio.estado.in_(ESTADOS_RESERVABLES),
            Espacio.aforo >= asistentes,
            Espacio.id.not_in(ocupados),
        )
        .order_by(Espacio.aforo, Espacio.id)
    )
    with db.obtener_sesion(motor_db) as sesion:
        return list(sesion.exec(consulta))
