"""Repositorio de reservas contra una base SQLite temporal."""

from datetime import datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoEspacio, EstadoReserva, Reserva
from nexo_campus.repositories import reservas as repo
from nexo_campus.services import reservas as servicio


def hora(h: int, dia: int = 15) -> datetime:
    return datetime(2030, 1, dia, h)


@pytest.fixture
def motor(tmp_path: Path):
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'prueba.db'}")
    db.crear_tablas(motor)
    with db.obtener_sesion(motor) as sesion:
        sesion.add_all([
            Espacio(id="AU-101", nombre="Aula 101", tipo="aula", aforo=30),
            Espacio(id="CU-01", nombre="Cubículo 1", tipo="cubiculo", aforo=4),
            Espacio(id="AU-102", nombre="Aula 102", tipo="aula", aforo=40, estado=EstadoEspacio.mantenimiento),
            Espacio(id="LAB-1", nombre="Laboratorio 1", tipo="laboratorio", aforo=20, estado=EstadoEspacio.inhabilitado),
        ])
        sesion.commit()
    return motor


def reservar(motor, espacio_id: str, inicio: datetime, fin: datetime, asistentes: int = 2, **campos) -> Reserva:
    reserva = Reserva(espacio_id=espacio_id, solicitante="Ana", inicio=inicio, fin=fin, asistentes=asistentes, **campos)
    return repo.guardar_reserva(reserva, motor_db=motor)


def test_obtener_espacio(motor):
    assert repo.obtener_espacio("AU-101", motor_db=motor).nombre == "Aula 101"
    assert repo.obtener_espacio("XX-999", motor_db=motor) is None


def test_guardar_crea_y_actualiza(motor):
    reserva = reservar(motor, "AU-101", hora(8), hora(10))
    assert reserva.id is not None

    reserva.asistentes = 12
    repo.guardar_reserva(reserva, motor_db=motor)

    assert repo.obtener_reserva(reserva.id, motor_db=motor).asistentes == 12
    assert len(repo.listar_reservas(motor_db=motor)) == 1


def test_listar_con_filtros(motor):
    reservar(motor, "AU-101", hora(8), hora(10))
    reservar(motor, "CU-01", hora(9), hora(11))
    reservar(motor, "AU-101", hora(8, dia=16), hora(10, dia=16))

    assert len(repo.listar_reservas(motor_db=motor)) == 3
    assert len(repo.listar_reservas(espacio_id="AU-101", motor_db=motor)) == 2
    assert len(repo.listar_reservas(desde=hora(0, dia=16), motor_db=motor)) == 1
    assert len(repo.listar_reservas(hasta=hora(0, dia=16), motor_db=motor)) == 2
    assert [r.espacio_id for r in repo.listar_reservas(desde=hora(10), hasta=hora(12), motor_db=motor)] == ["CU-01"]


def test_reservas_activas_en_franja(motor):
    existente = reservar(motor, "AU-101", hora(8), hora(10))
    reservar(motor, "AU-101", hora(12), hora(14), estado=EstadoReserva.cancelada)
    reservar(motor, "CU-01", hora(8), hora(10))

    assert [r.id for r in repo.reservas_activas_en_franja("AU-101", hora(9), hora(11), motor_db=motor)] == [existente.id]
    assert repo.reservas_activas_en_franja("AU-101", hora(10), hora(12), motor_db=motor) == []  # contigua
    assert repo.reservas_activas_en_franja("AU-101", hora(12), hora(14), motor_db=motor) == []  # cancelada
    assert repo.reservas_activas_en_franja("AU-101", hora(9), hora(11), excluir_id=existente.id, motor_db=motor) == []


def test_cancelar_reserva(motor):
    reserva = reservar(motor, "AU-101", hora(8), hora(10))

    cancelada = repo.cancelar_reserva(reserva.id, motor_db=motor)

    assert cancelada.estado is EstadoReserva.cancelada
    assert repo.obtener_reserva(reserva.id, motor_db=motor).estado is EstadoReserva.cancelada
    assert repo.reservas_activas_en_franja("AU-101", hora(8), hora(10), motor_db=motor) == []
    with pytest.raises(ReglaNegocioError, match="No existe la reserva #99"):
        repo.cancelar_reserva(99, motor_db=motor)


def test_espacios_disponibles(motor):
    reservar(motor, "CU-01", hora(8), hora(10))
    reservar(motor, "AU-101", hora(12), hora(14), estado=EstadoReserva.cancelada)

    def ids(inicio, fin, asistentes):
        return [e.id for e in repo.espacios_disponibles(inicio, fin, asistentes, motor_db=motor)]

    assert ids(hora(12), hora(14), 2) == ["CU-01", "AU-101"]  # habilitados, del más ajustado al más grande
    assert ids(hora(9), hora(11), 2) == ["AU-101"]  # CU-01 está ocupado
    assert ids(hora(10), hora(12), 2) == ["CU-01", "AU-101"]  # franja contigua
    assert ids(hora(12), hora(14), 10) == ["AU-101"]  # aforo
    assert ids(hora(12), hora(14), 35) == []  # AU-102 tiene aforo, pero está en mantenimiento


@pytest.fixture
def servicio_real(motor, monkeypatch):
    """El servicio de P2 usando este repositorio sobre la base temporal."""
    funciones = ("obtener_espacio", "obtener_reserva", "reservas_activas_en_franja", "guardar_reserva", "cancelar_reserva")
    monkeypatch.setattr(
        servicio, "repositorio", SimpleNamespace(**{f: partial(getattr(repo, f), motor_db=motor) for f in funciones})
    )
    return servicio


def test_servicio_con_repositorio_real(motor, servicio_real):
    reserva = servicio_real.crear_reserva("AU-101", "Ana", hora(8), hora(10), 10)
    with pytest.raises(ReglaNegocioError, match="ya está reservado"):
        servicio_real.crear_reserva("AU-101", "Luis", hora(9), hora(11), 10)

    servicio_real.modificar_reserva(reserva.id, hora(9), hora(11), 12)
    servicio_real.cancelar_reserva(reserva.id)

    guardada = repo.obtener_reserva(reserva.id, motor_db=motor)
    assert (guardada.inicio, guardada.asistentes, guardada.estado) == (hora(9), 12, EstadoReserva.cancelada)
    assert len(repo.listar_reservas(motor_db=motor)) == 1
