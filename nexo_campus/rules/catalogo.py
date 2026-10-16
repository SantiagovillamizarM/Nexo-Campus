"""Reglas para registrar y editar espacios y recursos desde la aplicación.

Funciones puras: no consultan la base de datos. Si una regla no se cumple, lanzan
ReglaNegocioError con un mensaje para el usuario final. Los límites se cambian en las constantes.
"""

import re

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import EstadoRecurso

PATRON_CODIGO = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")  # ej. AU-101, PC-001
AFORO_MAXIMO = 500
# 'prestado' no se elige a mano: solo lo asigna el registro de un préstamo.
ESTADOS_RECURSO_EDITABLES = (
    EstadoRecurso.disponible,
    EstadoRecurso.mantenimiento,
    EstadoRecurso.danado,
    EstadoRecurso.inhabilitado,
)


def normalizar_codigo(codigo: str) -> str:
    """Códigos en mayúsculas y sin espacios, con letras, números o guiones."""
    limpio = (codigo or "").strip().upper()
    if not PATRON_CODIGO.match(limpio):
        raise ReglaNegocioError(
            "El código debe tener entre 2 y 20 caracteres y solo letras, números o guiones (ej. AU-101)."
        )
    return limpio


def validar_texto_obligatorio(valor: str, campo: str) -> str:
    limpio = " ".join((valor or "").split())
    if not limpio:
        raise ReglaNegocioError(f"Indica el {campo}.")
    return limpio


def validar_codigo_libre(codigo: str, ya_existe: bool, entidad: str) -> None:
    if ya_existe:
        raise ReglaNegocioError(f"Ya existe un {entidad} con el código {codigo}.")


def validar_aforo_espacio(aforo: int) -> None:
    if not 1 <= aforo <= AFORO_MAXIMO:
        raise ReglaNegocioError(f"El aforo debe estar entre 1 y {AFORO_MAXIMO} personas.")


def validar_aforo_frente_a_reservas(aforo: int, mayor_reserva_futura: int) -> None:
    """No se puede bajar el aforo por debajo de una reserva activa futura ya aceptada."""
    if mayor_reserva_futura > aforo:
        raise ReglaNegocioError(
            f"Hay reservas activas para {mayor_reserva_futura} personas: el aforo no puede bajar a {aforo}."
        )


def validar_estado_recurso(nuevo: EstadoRecurso, actual: EstadoRecurso | None, tiene_prestamo_activo: bool) -> None:
    if nuevo not in ESTADOS_RECURSO_EDITABLES and nuevo is not actual:
        raise ReglaNegocioError("El estado 'Prestado' solo se asigna al registrar un préstamo.")
    if tiene_prestamo_activo and nuevo is not actual:
        raise ReglaNegocioError("El equipo tiene un préstamo activo: registra primero la devolución.")
