"""Servicio de reservas probado con un repositorio en memoria.

RepositorioEnMemoria implementa las mismas funciones que debe tener
nexo_campus/repositories/reservas.py, así que también sirve de referencia para ese archivo.
"""

import importlib.util
import sys
import types
from datetime import datetime

import pytest

# Mientras no exista el repositorio real, se registra un módulo vacío para poder importar el
# servicio. Las pruebas reemplazan el repositorio por el de memoria en cualquier caso.
if importlib.util.find_spec("nexo_campus.repositories.reservas") is None:
    sys.modules["nexo_campus.repositories.reservas"] = types.ModuleType("nexo_campus.repositories.reservas")

from nexo_campus.errors import ReglaNegocioError  # noqa: E402
from nexo_campus.models import Espacio, EstadoEspacio, EstadoReserva, Reserva  # noqa: E402
from nexo_campus.rules.reservas import se_solapan  # noqa: E402
from nexo_campus.services import reservas as servicio  # noqa: E402


class RepositorioEnMemoria:
    def __init__(self, espacios: list[Espacio]):
        self.espacios = {e.id: e for e in espacios}
        self.reservas: dict[int, Reserva] = {}
        self._siguiente_id = 1

    def obtener_espacio(self, espacio_id: str) -> Espacio | None:
        return self.espacios.get(espacio_id)

    def obtener_reserva(self, reserva_id: int) -> Reserva | None:
        return self.reservas.get(reserva_id)

    def reservas_activas_en_franja(
        self, espacio_id: str, inicio: datetime, fin: datetime, excluir_id: int | None = None
    ) -> list[Reserva]:
        return [
            r for r in self.reservas.values()
            if r.espacio_id == espacio_id
            and r.estado is EstadoReserva.activa
            and r.id != excluir_id
            and se_solapan(r.inicio, r.fin, inicio, fin)
        ]

    def guardar_reserva(self, reserva: Reserva) -> Reserva:
        if reserva.id is None:
            reserva.id = self._siguiente_id
            self._siguiente_id += 1
        self.reservas[reserva.id] = reserva
        return reserva

    def cancelar_reserva(self, reserva_id: int) -> Reserva:
        reserva = self.reservas[reserva_id]
        reserva.estado = EstadoReserva.cancelada
        return reserva


def hora(h: int) -> datetime:
    return datetime(2030, 1, 15, h)


@pytest.fixture
def repo(monkeypatch):
    repositorio = RepositorioEnMemoria([
        Espacio(id="AU-101", nombre="Aula 101", tipo="aula", aforo=30),
        Espacio(id="AU-102", nombre="Aula 102", tipo="aula", aforo=20, estado=EstadoEspacio.mantenimiento),
    ])
    monkeypatch.setattr(servicio, "repositorio", repositorio)
    return repositorio


def test_crear_reserva_valida(repo):
    reserva = servicio.crear_reserva("AU-101", "  Ana  Pérez ", hora(8), hora(10), 25, motivo="Clase")

    assert reserva.id == 1
    assert reserva.estado is EstadoReserva.activa
    assert reserva.solicitante == "Ana Pérez"
    assert repo.reservas[1] is reserva


@pytest.mark.parametrize(
    ("espacio_id", "inicio", "fin", "asistentes", "solicitante", "mensaje"),
    [
        ("XX-999", hora(8), hora(10), 5, "Ana", "No existe un espacio"),
        ("AU-102", hora(8), hora(10), 5, "Ana", "mantenimiento"),
        ("AU-101", hora(8), hora(10), 31, "Ana", "aforo"),
        ("AU-101", hora(10), hora(8), 5, "Ana", "posterior"),
        ("AU-101", hora(8), hora(10), 5, "   ", "quién solicita"),
    ],
)
def test_crear_reserva_invalida_no_guarda_nada(repo, espacio_id, inicio, fin, asistentes, solicitante, mensaje):
    with pytest.raises(ReglaNegocioError, match=mensaje):
        servicio.crear_reserva(espacio_id, solicitante, inicio, fin, asistentes)
    assert repo.reservas == {}


def test_no_permite_reservas_solapadas(repo):
    servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)

    with pytest.raises(ReglaNegocioError, match="ya está reservado"):
        servicio.crear_reserva("AU-101", "Luis", hora(9), hora(11), 10)
    assert len(repo.reservas) == 1


def test_permite_reservas_contiguas(repo):
    servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)
    servicio.crear_reserva("AU-101", "Luis", hora(10), hora(12), 10)
    assert len(repo.reservas) == 2


def test_modificar_no_choca_consigo_misma(repo):
    reserva = servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)

    modificada = servicio.modificar_reserva(reserva.id, hora(9), hora(11), 12)

    assert (modificada.inicio, modificada.fin, modificada.asistentes) == (hora(9), hora(11), 12)


def test_modificar_con_conflicto_deja_la_reserva_igual(repo):
    servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)
    segunda = servicio.crear_reserva("AU-101", "Luis", hora(12), hora(14), 10)

    with pytest.raises(ReglaNegocioError, match="ya está reservado"):
        servicio.modificar_reserva(segunda.id, hora(9), hora(11), 10)
    assert (segunda.inicio, segunda.fin) == (hora(12), hora(14))


def test_cancelar_libera_la_franja(repo):
    reserva = servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)

    servicio.cancelar_reserva(reserva.id)

    assert reserva.estado is EstadoReserva.cancelada
    servicio.crear_reserva("AU-101", "Luis", hora(8), hora(10), 10)


def test_no_se_cancela_ni_modifica_dos_veces(repo):
    reserva = servicio.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)
    servicio.cancelar_reserva(reserva.id)

    with pytest.raises(ReglaNegocioError, match="ya está cancelada"):
        servicio.cancelar_reserva(reserva.id)
    with pytest.raises(ReglaNegocioError, match="ya está cancelada"):
        servicio.modificar_reserva(reserva.id, hora(9), hora(11), 10)


def test_reserva_inexistente(repo):
    with pytest.raises(ReglaNegocioError, match="No existe la reserva #99"):
        servicio.cancelar_reserva(99)
