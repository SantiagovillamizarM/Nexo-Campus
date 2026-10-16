"""Entidades del dominio. Importar desde aquí: from nexo_campus.models import Espacio, EstadoEspacio."""

from nexo_campus.models.enums import (
    EstadoEspacio,
    EstadoIncidencia,
    EstadoPrestamo,
    EstadoRecurso,
    EstadoReserva,
    OrigenClasificacion,
    Prioridad,
    TipoInconsistencia,
)
from nexo_campus.models.espacio import Espacio
from nexo_campus.models.incidencia import Incidencia
from nexo_campus.models.inconsistencia import RegistroInconsistente
from nexo_campus.models.prestamo import Prestamo
from nexo_campus.models.recurso import Recurso
from nexo_campus.models.reserva import Reserva

__all__ = [
    "Espacio",
    "EstadoEspacio",
    "EstadoIncidencia",
    "EstadoPrestamo",
    "EstadoRecurso",
    "EstadoReserva",
    "Incidencia",
    "OrigenClasificacion",
    "Prestamo",
    "Prioridad",
    "Recurso",
    "RegistroInconsistente",
    "Reserva",
    "TipoInconsistencia",
]
