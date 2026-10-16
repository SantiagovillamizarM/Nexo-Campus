"""Casos de uso de las reservas: la UI llama a estas funciones.

Cada operación busca los datos con el repositorio, aplica todas las reglas de rules/reservas.py
y solo entonces guarda. Si algo no se cumple, lanza ReglaNegocioError y no se guarda nada.
"""

from dataclasses import dataclass, field
from datetime import datetime

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoRecurso, EstadoReserva, Recurso, Reserva
from nexo_campus.repositories import catalogo as repositorio_catalogo
from nexo_campus.repositories import reservas as repositorio
from nexo_campus.rules import reservas as reglas


@dataclass
class PcsDeSala:
    """Los PCs de una sala de cómputo: se prestan todos juntos al reservar la sala."""

    operativos: list[Recurso] = field(default_factory=list)
    fuera_de_servicio: list[Recurso] = field(default_factory=list)  # dañados, en mantenimiento o inhabilitados

    @property
    def total(self) -> int:
        return len(self.operativos) + len(self.fuera_de_servicio)


def _obtener_espacio(espacio_id: str) -> Espacio:
    espacio = repositorio.obtener_espacio(espacio_id)
    if espacio is None:
        raise ReglaNegocioError(f"No existe un espacio con el código '{espacio_id}'.")
    return espacio


def _obtener_reserva_activa(reserva_id: int) -> Reserva:
    reserva = repositorio.obtener_reserva(reserva_id)
    if reserva is None:
        raise ReglaNegocioError(f"No existe la reserva #{reserva_id}.")
    if reserva.estado is EstadoReserva.cancelada:
        raise ReglaNegocioError(f"La reserva #{reserva_id} ya está cancelada.")
    return reserva


def _validar(
    espacio: Espacio, inicio: datetime, fin: datetime, asistentes: int, excluir_id: int | None = None
) -> None:
    reglas.validar_espacio_habilitado(espacio)
    reglas.validar_horario(inicio, fin, ahora=datetime.now())
    reglas.validar_aforo(asistentes, espacio.aforo)
    conflictos = repositorio.reservas_activas_en_franja(espacio.id, inicio, fin, excluir_id=excluir_id)
    reglas.validar_sin_solapamiento(conflictos)


def _limpiar_solicitante(solicitante: str) -> str:
    limpio = " ".join((solicitante or "").split())
    if not limpio:
        raise ReglaNegocioError("Indica quién solicita la reserva.")
    return limpio


def crear_reserva(
    espacio_id: str,
    solicitante: str,
    inicio: datetime,
    fin: datetime,
    asistentes: int,
    motivo: str | None = None,
) -> Reserva:
    espacio = _obtener_espacio(espacio_id)
    reserva = Reserva(
        espacio_id=espacio.id,
        solicitante=_limpiar_solicitante(solicitante),
        inicio=inicio,
        fin=fin,
        asistentes=asistentes,
        motivo=(motivo or "").strip() or None,
        estado=EstadoReserva.activa,
    )
    _validar(espacio, inicio, fin, asistentes)
    return repositorio.guardar_reserva(reserva)


def modificar_reserva(
    reserva_id: int,
    inicio: datetime,
    fin: datetime,
    asistentes: int,
    espacio_id: str | None = None,
    motivo: str | None = None,
) -> Reserva:
    """Cambia la franja, los asistentes o el espacio. La reserva no choca consigo misma."""
    reserva = _obtener_reserva_activa(reserva_id)
    espacio = _obtener_espacio(espacio_id or reserva.espacio_id)
    _validar(espacio, inicio, fin, asistentes, excluir_id=reserva.id)

    reserva.espacio_id = espacio.id
    reserva.inicio = inicio
    reserva.fin = fin
    reserva.asistentes = asistentes
    if motivo is not None:
        reserva.motivo = motivo.strip() or None
    return repositorio.guardar_reserva(reserva)


def cancelar_reserva(reserva_id: int) -> Reserva:
    _obtener_reserva_activa(reserva_id)
    return repositorio.cancelar_reserva(reserva_id)


# --- PCs de las salas de cómputo -----------------------------------------------------------------
# Los PCs de torre no se prestan sueltos: reservar una sala de cómputo es el préstamo de todos sus PCs
# durante la franja de la reserva.


def pcs_de_la_sala(espacio_id: str) -> PcsDeSala:
    espacio = repositorio.obtener_espacio(espacio_id)
    if espacio is None:
        return PcsDeSala()
    pcs = PcsDeSala()
    for recurso in repositorio_catalogo.recursos_en_espacio(espacio):
        (pcs.operativos if recurso.estado is EstadoRecurso.disponible else pcs.fuera_de_servicio).append(recurso)
    return pcs


def prestamos_de_salas(desde: datetime | None = None) -> list[tuple[Reserva, Espacio, PcsDeSala]]:
    """Reservas activas (en curso o futuras) de salas con PCs: cada una presta los PCs de su sala."""
    desde = desde or datetime.now()
    resultado = []
    for reserva in repositorio.listar_reservas(desde=desde):
        if reserva.estado is not EstadoReserva.activa:
            continue
        pcs = pcs_de_la_sala(reserva.espacio_id)
        if pcs.total:
            resultado.append((reserva, repositorio.obtener_espacio(reserva.espacio_id), pcs))
    return resultado


def pcs_en_uso(ahora: datetime | None = None) -> dict[str, Reserva]:
    """PCs que están prestados en este momento porque su sala tiene una reserva en curso."""
    ahora = ahora or datetime.now()
    en_uso = {}
    for reserva, _espacio, pcs in prestamos_de_salas(desde=ahora):
        if reserva.inicio <= ahora < reserva.fin:
            for pc in pcs.operativos:
                en_uso[pc.id] = reserva
    return en_uso
