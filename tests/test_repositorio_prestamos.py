"""Repositorio de préstamos e historial de estados contra una base SQLite temporal."""

from datetime import datetime
from pathlib import Path

import pytest

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import EstadoPrestamo, EstadoRecurso, OrigenCambioEstado, Prestamo, Recurso
from nexo_campus.repositories import prestamos as repo


@pytest.fixture
def motor(tmp_path: Path):
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'prueba.db'}")
    db.crear_tablas(motor)
    with db.obtener_sesion(motor) as sesion:
        sesion.add_all([
            Recurso(id="PC-01", nombre="Portátil 1", tipo="portatil"),
            Recurso(id="PC-02", nombre="Portátil 2", tipo="portatil"),
            Recurso(id="PR-01", nombre="Proyector", tipo="proyector", estado=EstadoRecurso.danado),
        ])
        sesion.commit()
    return motor


def prestar(motor, recurso_id: str, solicitante: str = "Ana", dia: int = 15, **campos) -> Prestamo:
    prestamo = Prestamo(recurso_id=recurso_id, solicitante=solicitante, fecha_prestamo=datetime(2030, 1, dia, 8), **campos)
    return repo.guardar_prestamo(prestamo, motor_db=motor)


def test_obtener_recurso_y_prestamo(motor):
    prestamo = prestar(motor, "PC-01")

    assert repo.obtener_recurso("PC-01", motor_db=motor).nombre == "Portátil 1"
    assert repo.obtener_recurso("XX-1", motor_db=motor) is None
    assert repo.obtener_prestamo(prestamo.id, motor_db=motor).recurso_id == "PC-01"
    assert repo.obtener_prestamo(99, motor_db=motor) is None


def test_guardar_crea_y_actualiza(motor):
    prestamo = prestar(motor, "PC-01")
    assert prestamo.id is not None

    prestamo.estado = EstadoPrestamo.devuelto
    prestamo.fecha_devolucion = datetime(2030, 1, 15, 12)
    repo.guardar_prestamo(prestamo, motor_db=motor)

    guardado = repo.obtener_prestamo(prestamo.id, motor_db=motor)
    assert guardado.estado is EstadoPrestamo.devuelto
    assert len(repo.listar_prestamos(motor_db=motor)) == 1


def test_prestamo_activo_de_recurso(motor):
    prestar(motor, "PC-01", estado=EstadoPrestamo.devuelto)
    assert repo.prestamo_activo_de_recurso("PC-01", motor_db=motor) is None

    activo = prestar(motor, "PC-01", dia=16)
    assert repo.prestamo_activo_de_recurso("PC-01", motor_db=motor).id == activo.id


def test_prestamos_activos_de_persona(motor):
    prestar(motor, "PC-01", solicitante="Ana Pérez")
    prestar(motor, "PC-02", solicitante="ana pérez ")
    prestar(motor, "PR-01", solicitante="Ana Pérez", estado=EstadoPrestamo.devuelto)
    prestar(motor, "PR-01", solicitante="Luis", dia=16)

    assert len(repo.prestamos_activos_de("  Ana   Pérez", motor_db=motor)) == 2
    assert len(repo.prestamos_activos_de("Luis", motor_db=motor)) == 1
    assert repo.prestamos_activos_de("Nadie", motor_db=motor) == []


def test_listar_prestamos(motor):
    prestar(motor, "PC-01", dia=15)
    prestar(motor, "PC-02", dia=16)
    prestar(motor, "PR-01", dia=14, estado=EstadoPrestamo.devuelto)

    assert [p.recurso_id for p in repo.listar_prestamos(motor_db=motor)] == ["PC-02", "PC-01", "PR-01"]
    assert [p.recurso_id for p in repo.listar_prestamos(activos=True, motor_db=motor)] == ["PC-02", "PC-01"]
    assert [p.recurso_id for p in repo.listar_prestamos(activos=False, motor_db=motor)] == ["PR-01"]


def test_cambiar_estado_escribe_historial(motor):
    recurso = repo.cambiar_estado_recurso(
        "PC-01", EstadoRecurso.prestado, "Préstamo a Ana", OrigenCambioEstado.prestamo, motor_db=motor
    )
    repo.cambiar_estado_recurso("PC-01", EstadoRecurso.danado, "Pantalla rota", OrigenCambioEstado.devolucion, motor_db=motor)

    assert recurso.estado is EstadoRecurso.prestado
    assert repo.obtener_recurso("PC-01", motor_db=motor).estado is EstadoRecurso.danado
    historial = repo.listar_historial("PC-01", motor_db=motor)
    assert [(h.estado_anterior, h.estado_nuevo, h.origen) for h in historial] == [
        (EstadoRecurso.prestado, EstadoRecurso.danado, OrigenCambioEstado.devolucion),  # el más reciente primero
        (EstadoRecurso.disponible, EstadoRecurso.prestado, OrigenCambioEstado.prestamo),
    ]
    assert repo.listar_historial("PC-02", motor_db=motor) == []


def test_cambiar_al_mismo_estado_no_escribe_historial(motor):
    repo.cambiar_estado_recurso("PC-01", EstadoRecurso.disponible, None, OrigenCambioEstado.devolucion, motor_db=motor)
    assert repo.listar_historial("PC-01", motor_db=motor) == []


def test_cambiar_estado_de_recurso_inexistente(motor):
    with pytest.raises(ReglaNegocioError, match="No existe un recurso"):
        repo.cambiar_estado_recurso("XX-1", EstadoRecurso.danado, None, OrigenCambioEstado.incidencia, motor_db=motor)
