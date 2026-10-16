"""Repositorio de incidencias contra una base SQLite temporal."""

from pathlib import Path

import pytest

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoIncidencia, Incidencia, OrigenClasificacion, Prioridad, Recurso
from nexo_campus.repositories import incidencias as repo


@pytest.fixture
def motor(tmp_path: Path):
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'prueba.db'}")
    db.crear_tablas(motor)
    with db.obtener_sesion(motor) as sesion:
        sesion.add_all([
            Espacio(id="AU-101", nombre="Aula 101", tipo="aula", aforo=30),
            Recurso(id="PR-01", nombre="Proyector", tipo="proyector"),
        ])
        sesion.commit()
    return motor


def reportar(motor, descripcion: str = "El proyector no enciende", **campos) -> Incidencia:
    return repo.guardar_incidencia(Incidencia(descripcion=descripcion, **campos), motor_db=motor)


def test_guardar_y_obtener(motor):
    incidencia = reportar(
        motor, espacio_id="AU-101", recurso_id="PR-01", categoria="tecnologia", prioridad=Prioridad.alta,
        area_responsable="soporte_ti", justificacion="Bloquea la clase", origen_clasificacion=OrigenClasificacion.ia,
    )

    guardada = repo.obtener_incidencia(incidencia.id, motor_db=motor)
    assert guardada.prioridad is Prioridad.alta
    assert guardada.origen_clasificacion is OrigenClasificacion.ia
    assert guardada.estado is EstadoIncidencia.abierta
    assert repo.obtener_incidencia(99, motor_db=motor) is None


def test_listar_con_filtros(motor):
    reportar(motor, "Uno", prioridad=Prioridad.alta)
    reportar(motor, "Dos", prioridad=Prioridad.baja, estado=EstadoIncidencia.cerrada)
    reportar(motor, "Tres", prioridad=Prioridad.alta, estado=EstadoIncidencia.cerrada)

    assert [i.descripcion for i in repo.listar_incidencias(motor_db=motor)] == ["Tres", "Dos", "Uno"]
    assert [i.descripcion for i in repo.listar_incidencias(prioridad=Prioridad.alta, motor_db=motor)] == ["Tres", "Uno"]
    assert [
        i.descripcion
        for i in repo.listar_incidencias(estado=EstadoIncidencia.cerrada, prioridad=Prioridad.baja, motor_db=motor)
    ] == ["Dos"]


def test_cerrar_incidencia(motor):
    incidencia = reportar(motor)

    cerrada = repo.cerrar_incidencia(incidencia.id, motor_db=motor)

    assert cerrada.estado is EstadoIncidencia.cerrada
    assert cerrada.fecha_cierre is not None
    assert repo.obtener_incidencia(incidencia.id, motor_db=motor).fecha_cierre is not None
    with pytest.raises(ReglaNegocioError, match="No existe la incidencia #99"):
        repo.cerrar_incidencia(99, motor_db=motor)


def test_incidencias_abiertas_de(motor):
    del_espacio = reportar(motor, "Silla rota", espacio_id="AU-101")
    del_proyector = reportar(motor, "No enciende", espacio_id="AU-101", recurso_id="PR-01", estado=EstadoIncidencia.en_proceso)
    reportar(motor, "Ya resuelta", espacio_id="AU-101", estado=EstadoIncidencia.cerrada)
    general = reportar(motor, "Baños sin agua")

    def ids(**filtros):
        return [i.id for i in repo.incidencias_abiertas_de(motor_db=motor, **filtros)]

    assert ids(espacio_id="AU-101") == [del_espacio.id, del_proyector.id]  # en proceso cuenta como abierta
    assert ids(recurso_id="PR-01") == [del_proyector.id]
    assert ids() == [del_espacio.id, del_proyector.id, general.id]
    assert ids(espacio_id="CU-01") == []
