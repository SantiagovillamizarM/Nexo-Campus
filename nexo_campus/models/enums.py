"""Estados y categorías del dominio.

Son la única fuente de verdad: nadie escribe estos valores como texto suelto.
Los valores coinciden con los nombres (en minúsculas) para que SQLite guarde el mismo texto.
"""

from enum import Enum


class EstadoEspacio(str, Enum):
    disponible = "disponible"
    mantenimiento = "mantenimiento"
    inhabilitado = "inhabilitado"


class EstadoRecurso(str, Enum):
    disponible = "disponible"
    prestado = "prestado"
    mantenimiento = "mantenimiento"
    danado = "danado"
    inhabilitado = "inhabilitado"


class EstadoReserva(str, Enum):
    activa = "activa"
    cancelada = "cancelada"


class EstadoPrestamo(str, Enum):
    activo = "activo"
    devuelto = "devuelto"


class EstadoIncidencia(str, Enum):
    abierta = "abierta"
    en_proceso = "en_proceso"
    cerrada = "cerrada"


class Prioridad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class OrigenClasificacion(str, Enum):
    """Quién clasificó la incidencia. Nunca se marca como 'ia' algo que no hizo la IA."""

    ia = "ia"
    manual = "manual"
    datos_origen = "datos_origen"


class OrigenCambioEstado(str, Enum):
    """Qué provocó un cambio de estado de un recurso (queda en el historial)."""

    carga = "carga"
    prestamo = "prestamo"
    devolucion = "devolucion"
    incidencia = "incidencia"
    edicion = "edicion"  # una persona cambió el estado desde la pantalla de administración


class TipoInconsistencia(str, Enum):
    rechazado = "rechazado"  # el registro NO se cargó
    advertencia = "advertencia"  # se cargó, pero con un dato corregido o dudoso
