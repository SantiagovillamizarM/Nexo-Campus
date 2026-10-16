"""Reglas de negocio de las reservas de espacios.

Funciones puras: no consultan la base de datos ni la IA. Si una regla no se cumple, lanzan
ReglaNegocioError con un mensaje para el usuario final. Los límites se cambian en las constantes.
"""

from collections.abc import Sequence
from datetime import datetime, time, timedelta

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoEspacio, Reserva

HORA_APERTURA = time(6, 0)
HORA_CIERRE = time(22, 0)
DURACION_MINIMA_MINUTOS = 30
DURACION_MAXIMA_HORAS = 4
ESTADOS_RESERVABLES = {EstadoEspacio.disponible}


def se_solapan(inicio_a: datetime, fin_a: datetime, inicio_b: datetime, fin_b: datetime) -> bool:
    """Dos franjas se cruzan si cada una empieza antes de que termine la otra (08-10 y 10-12 no se cruzan)."""
    return inicio_a < fin_b and inicio_b < fin_a


def validar_horario(inicio: datetime, fin: datetime, ahora: datetime | None = None) -> None:
    """La franja es coherente, está dentro del horario del campus y no está en el pasado."""
    if fin <= inicio:
        raise ReglaNegocioError("La hora de fin debe ser posterior a la hora de inicio.")
    if inicio.date() != fin.date():
        raise ReglaNegocioError("La reserva debe empezar y terminar el mismo día.")
    if inicio.time() < HORA_APERTURA or fin.time() > HORA_CIERRE:
        raise ReglaNegocioError(
            f"Los espacios solo se pueden reservar entre las {HORA_APERTURA:%H:%M} y las {HORA_CIERRE:%H:%M}."
        )

    duracion = fin - inicio
    if duracion < timedelta(minutes=DURACION_MINIMA_MINUTOS):
        raise ReglaNegocioError(f"La reserva debe durar al menos {DURACION_MINIMA_MINUTOS} minutos.")
    if duracion > timedelta(hours=DURACION_MAXIMA_HORAS):
        raise ReglaNegocioError(f"La reserva no puede durar más de {DURACION_MAXIMA_HORAS} horas.")

    if ahora is not None and inicio < ahora:
        raise ReglaNegocioError("No se puede reservar una franja que ya empezó o que está en el pasado.")


def validar_aforo(asistentes: int, aforo: int) -> None:
    """Regla 2: el número de asistentes no supera el aforo del espacio."""
    if asistentes < 1:
        raise ReglaNegocioError("La reserva debe tener al menos 1 asistente.")
    if asistentes > aforo:
        raise ReglaNegocioError(
            f"El espacio tiene un aforo de {aforo} personas y la reserva es para {asistentes}."
        )


def validar_espacio_habilitado(espacio: Espacio) -> None:
    """Regla 3: no se reservan espacios en mantenimiento o inhabilitados."""
    if espacio.estado not in ESTADOS_RESERVABLES:
        raise ReglaNegocioError(
            f"El espacio {espacio.nombre} ({espacio.id}) está en estado '{espacio.estado.value}' "
            "y no se puede reservar."
        )


def validar_sin_solapamiento(reservas_en_conflicto: Sequence[Reserva]) -> None:
    """Regla 1: no puede haber otra reserva activa del mismo espacio en la misma franja.

    Recibe las reservas activas que se cruzan con la franja pedida (las busca el repositorio).
    """
    if not reservas_en_conflicto:
        return
    otra = min(reservas_en_conflicto, key=lambda reserva: reserva.inicio)
    mensaje = (
        f"El espacio ya está reservado el {otra.inicio:%d/%m/%Y} "
        f"de {otra.inicio:%H:%M} a {otra.fin:%H:%M} por {otra.solicitante}."
    )
    if len(reservas_en_conflicto) > 1:
        mensaje += f" Hay {len(reservas_en_conflicto)} reservas que se cruzan con esa franja."
    raise ReglaNegocioError(mensaje)
