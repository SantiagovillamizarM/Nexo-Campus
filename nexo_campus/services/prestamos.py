"""Casos de uso de los préstamos: la UI llama a estas funciones.

Cada operación busca los datos con el repositorio, aplica las reglas de rules/prestamos.py y solo
entonces guarda. Cada cambio de estado del equipo queda en su historial.
"""

from datetime import datetime

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import EstadoPrestamo, EstadoRecurso, OrigenCambioEstado, Prestamo
from nexo_campus.repositories import prestamos as repositorio
from nexo_campus.rules import prestamos as reglas
from nexo_campus.services import regla_central


def _limpiar_solicitante(solicitante: str) -> str:
    limpio = " ".join((solicitante or "").split())
    if not limpio:
        raise ReglaNegocioError("Indica a quién se le presta el equipo.")
    return limpio


def prestar_recurso(recurso_id: str, solicitante: str, fecha_devolucion_prevista: datetime) -> Prestamo:
    recurso = repositorio.obtener_recurso(recurso_id)
    if recurso is None:
        raise ReglaNegocioError(f"No existe un equipo con el código '{recurso_id}'.")
    solicitante = _limpiar_solicitante(solicitante)

    reglas.validar_recurso_prestable(recurso)  # regla 4 (incluye los bloqueados por una incidencia)
    if repositorio.prestamo_activo_de_recurso(recurso_id) is not None:
        raise ReglaNegocioError(f"{recurso.nombre} ({recurso_id}) ya tiene un préstamo activo.")
    reglas.validar_limite_prestamos(len(repositorio.prestamos_activos_de(solicitante)))  # regla 5
    ahora = datetime.now()
    reglas.validar_fecha_devolucion(ahora, fecha_devolucion_prevista)

    prestamo = repositorio.guardar_prestamo(
        Prestamo(
            recurso_id=recurso_id,
            solicitante=solicitante,
            fecha_prestamo=ahora,
            fecha_devolucion_prevista=fecha_devolucion_prevista,
            estado=EstadoPrestamo.activo,
        )
    )
    repositorio.cambiar_estado_recurso(recurso_id, EstadoRecurso.prestado, f"Prestado a {solicitante}", OrigenCambioEstado.prestamo)
    return prestamo


def devolver_recurso(prestamo_id: int, estado_final: EstadoRecurso, observacion: str | None = None) -> Prestamo:
    """Cierra el préstamo. El equipo queda disponible o dañado; si tiene una incidencia grave abierta, queda bloqueado."""
    prestamo = repositorio.obtener_prestamo(prestamo_id)
    if prestamo is None:
        raise ReglaNegocioError(f"No existe el préstamo #{prestamo_id}.")
    if prestamo.estado is not EstadoPrestamo.activo:
        raise ReglaNegocioError(f"El préstamo #{prestamo_id} ya fue devuelto.")
    reglas.validar_estado_devolucion(estado_final)

    prestamo.estado = EstadoPrestamo.devuelto
    prestamo.fecha_devolucion = datetime.now()
    devuelto = repositorio.guardar_prestamo(prestamo)

    nota = " ".join((observacion or "").split())
    motivo = nota or ("Devuelto en buen estado" if estado_final is EstadoRecurso.disponible else "Devuelto con daños")
    repositorio.cambiar_estado_recurso(prestamo.recurso_id, estado_final, motivo, OrigenCambioEstado.devolucion)
    if regla_central.recurso_bloqueado(prestamo.recurso_id):
        # Primero se registra cómo volvió y luego el bloqueo: al cerrar la incidencia, vuelve a ese estado.
        repositorio.cambiar_estado_recurso(
            prestamo.recurso_id, EstadoRecurso.inhabilitado,
            "Bloqueado al devolverse: tiene una incidencia grave abierta", OrigenCambioEstado.incidencia,
        )
    return devuelto
