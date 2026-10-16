"""Reglas de negocio de los préstamos de equipos.

Funciones puras: no consultan la base de datos ni la IA. Si una regla no se cumple, lanzan
ReglaNegocioError con un mensaje para el usuario final. Los límites se cambian en las constantes.
"""

from datetime import datetime, timedelta

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import EstadoRecurso, Recurso

MAX_PRESTAMOS_ACTIVOS = 2  # préstamos simultáneos por persona
DIAS_MAXIMOS_PRESTAMO = 7
TIPOS_NO_PRESTABLES = {"pc_torre"}  # no se prestan sueltos: se prestan junto con su sala al reservarla
ESTADOS_PRESTABLES = {EstadoRecurso.disponible}
ESTADOS_DEVOLUCION = (EstadoRecurso.disponible, EstadoRecurso.danado)


def validar_recurso_prestable(recurso: Recurso) -> None:
    """Regla 4: solo se presta un equipo disponible y de un tipo que se pueda llevar."""
    if recurso.tipo in TIPOS_NO_PRESTABLES:
        sala = f"la sala {recurso.ubicacion}" if recurso.ubicacion else "su sala"
        raise ReglaNegocioError(
            f"{recurso.nombre} ({recurso.id}) no se presta por separado: se presta junto con todos los PCs "
            f"de {sala} al reservarla en Espacios."
        )
    if recurso.estado not in ESTADOS_PRESTABLES:
        raise ReglaNegocioError(
            f"{recurso.nombre} ({recurso.id}) está en estado '{recurso.estado.value}' y no se puede prestar."
        )


def validar_limite_prestamos(prestamos_activos: int) -> None:
    """Regla 5: una persona no puede tener más de MAX_PRESTAMOS_ACTIVOS equipos a la vez."""
    if prestamos_activos >= MAX_PRESTAMOS_ACTIVOS:
        raise ReglaNegocioError(
            f"La persona ya tiene {prestamos_activos} préstamos activos (máximo permitido: {MAX_PRESTAMOS_ACTIVOS}). "
            "Debe devolver uno antes de pedir otro."
        )


def validar_fecha_devolucion(fecha_prestamo: datetime, devolucion_prevista: datetime) -> None:
    if devolucion_prevista <= fecha_prestamo:
        raise ReglaNegocioError("La devolución prevista debe ser posterior al momento del préstamo.")
    if devolucion_prevista - fecha_prestamo > timedelta(days=DIAS_MAXIMOS_PRESTAMO):
        raise ReglaNegocioError(f"Un préstamo no puede durar más de {DIAS_MAXIMOS_PRESTAMO} días.")


def validar_estado_devolucion(estado_final: EstadoRecurso) -> None:
    if estado_final not in ESTADOS_DEVOLUCION:
        raise ReglaNegocioError("Al devolverse, el equipo solo puede quedar disponible o dañado.")
