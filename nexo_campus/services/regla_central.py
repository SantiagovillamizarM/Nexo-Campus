"""Regla central: las incidencias graves bloquean espacios y equipos, y al cerrarse los liberan.

Así los tres módulos operan juntos: un espacio con una incidencia grave abierta no se puede
reservar (regla 3) y un equipo no se puede prestar (regla 4), porque quedan inhabilitados.
Cada bloqueo y liberación queda en el historial del espacio o del equipo.
"""

from dataclasses import dataclass, field
from datetime import datetime

from nexo_campus.models import (
    EstadoEspacio,
    EstadoRecurso,
    EstadoReserva,
    Incidencia,
    OrigenCambioEstado,
    Reserva,
)
from nexo_campus.repositories import catalogo as repositorio_catalogo
from nexo_campus.repositories import incidencias as repositorio_incidencias
from nexo_campus.repositories import prestamos as repositorio_prestamos
from nexo_campus.repositories import reservas as repositorio_reservas
from nexo_campus.rules import central as reglas


@dataclass
class EfectoBloqueo:
    espacio_bloqueado: str | None = None
    recurso_bloqueado: str | None = None
    recurso_prestado: str | None = None  # se bloqueará cuando se devuelva
    reservas_afectadas: list[Reserva] = field(default_factory=list)  # activas a futuro en el espacio bloqueado


def _motivo(incidencia: Incidencia) -> str:
    resumen = incidencia.descripcion if len(incidencia.descripcion) <= 80 else incidencia.descripcion[:77] + "..."
    return f"Incidencia #{incidencia.id} ({incidencia.prioridad.value}): {resumen}"


def _hay_otra_bloqueante(incidencia: Incidencia, espacio_id: str | None = None, recurso_id: str | None = None) -> bool:
    abiertas = repositorio_incidencias.incidencias_abiertas_de(espacio_id=espacio_id, recurso_id=recurso_id)
    return any(i.id != incidencia.id and reglas.bloquea(i.prioridad) for i in abiertas)


def bloquear_por_incidencia(incidencia: Incidencia) -> EfectoBloqueo:
    """Se llama al registrar una incidencia. Si es grave, inhabilita lo afectado."""
    efecto = EfectoBloqueo()
    if not reglas.bloquea(incidencia.prioridad):
        return efecto

    if incidencia.espacio_id:
        espacio = repositorio_reservas.obtener_espacio(incidencia.espacio_id)
        if espacio is not None and espacio.estado is not EstadoEspacio.inhabilitado:
            repositorio_catalogo.cambiar_estado_espacio(
                espacio.id, EstadoEspacio.inhabilitado, _motivo(incidencia), OrigenCambioEstado.incidencia
            )
            efecto.espacio_bloqueado = espacio.id
        efecto.reservas_afectadas = reservas_por_reubicar(incidencia.espacio_id)

    if incidencia.recurso_id:
        recurso = repositorio_prestamos.obtener_recurso(incidencia.recurso_id)
        if recurso is not None and recurso.estado is EstadoRecurso.prestado:
            efecto.recurso_prestado = recurso.id  # no se le quita a quien lo tiene: se bloquea al devolverse
        elif recurso is not None and recurso.estado is not EstadoRecurso.inhabilitado:
            repositorio_prestamos.cambiar_estado_recurso(
                recurso.id, EstadoRecurso.inhabilitado, _motivo(incidencia), OrigenCambioEstado.incidencia
            )
            efecto.recurso_bloqueado = recurso.id
    return efecto


def liberar_por_cierre(incidencia: Incidencia) -> list[str]:
    """Se llama al cerrar una incidencia. Devuelve los códigos que volvieron a su estado anterior.

    Solo se libera lo que bloqueó una incidencia (según el historial) y si no queda otra incidencia
    grave abierta sobre lo mismo. Un espacio que ya estaba inhabilitado por otra razón no se toca.
    """
    if not reglas.bloquea(incidencia.prioridad):
        return []
    liberados = []

    if incidencia.espacio_id and not _hay_otra_bloqueante(incidencia, espacio_id=incidencia.espacio_id):
        espacio = repositorio_reservas.obtener_espacio(incidencia.espacio_id)
        historial = repositorio_catalogo.listar_historial_espacio(incidencia.espacio_id)
        ultimo = historial[0] if historial else None
        if (
            espacio is not None and espacio.estado is EstadoEspacio.inhabilitado
            and ultimo is not None and ultimo.origen is OrigenCambioEstado.incidencia
            and ultimo.estado_nuevo is EstadoEspacio.inhabilitado
        ):
            repositorio_catalogo.cambiar_estado_espacio(
                espacio.id, ultimo.estado_anterior, f"Incidencia #{incidencia.id} cerrada", OrigenCambioEstado.incidencia
            )
            liberados.append(espacio.id)

    if incidencia.recurso_id and not _hay_otra_bloqueante(incidencia, recurso_id=incidencia.recurso_id):
        recurso = repositorio_prestamos.obtener_recurso(incidencia.recurso_id)
        historial = repositorio_prestamos.listar_historial(incidencia.recurso_id)
        ultimo = historial[0] if historial else None
        if (
            recurso is not None and recurso.estado is EstadoRecurso.inhabilitado
            and ultimo is not None and ultimo.origen is OrigenCambioEstado.incidencia
            and ultimo.estado_nuevo is EstadoRecurso.inhabilitado
        ):
            repositorio_prestamos.cambiar_estado_recurso(
                recurso.id, ultimo.estado_anterior, f"Incidencia #{incidencia.id} cerrada", OrigenCambioEstado.incidencia
            )
            liberados.append(recurso.id)
    return liberados


def recurso_bloqueado(recurso_id: str) -> bool:
    """True si el equipo tiene una incidencia grave abierta (se usa al devolverlo)."""
    return any(reglas.bloquea(i.prioridad) for i in repositorio_incidencias.incidencias_abiertas_de(recurso_id=recurso_id))


def reservas_por_reubicar(espacio_id: str) -> list[Reserva]:
    """Reservas activas a futuro de un espacio inhabilitado: hay que avisar y reubicar."""
    return [
        r for r in repositorio_reservas.listar_reservas(espacio_id=espacio_id, desde=datetime.now())
        if r.estado is EstadoReserva.activa
    ]


def describir_bloqueo(incidencia: Incidencia) -> str | None:
    """Texto para la UI con lo que quedó bloqueado por la incidencia (None si no bloquea nada)."""
    if not reglas.bloquea(incidencia.prioridad):
        return None
    partes = []
    if incidencia.espacio_id:
        espacio = repositorio_reservas.obtener_espacio(incidencia.espacio_id)
        if espacio is not None and espacio.estado is EstadoEspacio.inhabilitado:
            partes.append(f"{espacio.nombre} quedó inhabilitado para reservas")
            pendientes = reservas_por_reubicar(espacio.id)
            if pendientes:
                partes.append(f"{len(pendientes)} reserva(s) activa(s) deben reubicarse")
    if incidencia.recurso_id:
        recurso = repositorio_prestamos.obtener_recurso(incidencia.recurso_id)
        if recurso is not None and recurso.estado is EstadoRecurso.inhabilitado:
            partes.append(f"{recurso.nombre} ({recurso.id}) quedó inhabilitado")
        elif recurso is not None and recurso.estado is EstadoRecurso.prestado:
            partes.append(f"{recurso.nombre} ({recurso.id}) se bloqueará cuando se devuelva")
    return "; ".join(partes) or None


def describir_liberacion(incidencia: Incidencia) -> str | None:
    """Texto para la UI con lo que volvió a estar disponible al cerrar la incidencia."""
    if not reglas.bloquea(incidencia.prioridad):
        return None
    partes = []
    if incidencia.espacio_id:
        espacio = repositorio_reservas.obtener_espacio(incidencia.espacio_id)
        if espacio is not None and espacio.estado is not EstadoEspacio.inhabilitado:
            partes.append(f"{espacio.nombre} vuelve a estar en estado '{espacio.estado.value}'")
    if incidencia.recurso_id:
        recurso = repositorio_prestamos.obtener_recurso(incidencia.recurso_id)
        if recurso is not None and recurso.estado is not EstadoRecurso.inhabilitado:
            partes.append(f"{recurso.nombre} vuelve a estar en estado '{recurso.estado.value}'")
    return "; ".join(partes) or None
