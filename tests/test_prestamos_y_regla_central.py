"""Préstamos (reglas 4 y 5) y regla central (incidencias graves bloquean espacios y equipos), sobre SQLite temporal."""

import inspect
from datetime import datetime, timedelta

import pytest

from nexo_campus import db
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import (
    Espacio,
    EstadoEspacio,
    EstadoPrestamo,
    EstadoRecurso,
    OrigenCambioEstado,
    OrigenClasificacion,
    Prioridad,
    Recurso,
)
from nexo_campus.rules import prestamos as reglas
from nexo_campus.services import incidencias as servicio_incidencias
from nexo_campus.services import prestamos as servicio
from nexo_campus.services import regla_central
from nexo_campus.services import reservas as servicio_reservas

MANANA = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)


# --- Reglas puras --------------------------------------------------------------------------------


def portatil(estado=EstadoRecurso.disponible, tipo="portatil"):
    return Recurso(id="PT-01", nombre="Portátil 1", tipo=tipo, estado=estado)


def test_regla4_equipo_disponible_se_puede_prestar():
    reglas.validar_recurso_prestable(portatil())


@pytest.mark.parametrize(
    ("recurso", "mensaje"),
    [
        (portatil(tipo="pc_torre"), "no se presta por separado"),
        (portatil(EstadoRecurso.prestado), "'prestado'"),
        (portatil(EstadoRecurso.mantenimiento), "'mantenimiento'"),
        (portatil(EstadoRecurso.danado), "'danado'"),
        (portatil(EstadoRecurso.inhabilitado), "'inhabilitado'"),
    ],
)
def test_regla4_equipo_no_prestable(recurso, mensaje):
    with pytest.raises(ReglaNegocioError, match=mensaje):
        reglas.validar_recurso_prestable(recurso)


def test_regla5_limite_de_prestamos():
    reglas.validar_limite_prestamos(reglas.MAX_PRESTAMOS_ACTIVOS - 1)
    with pytest.raises(ReglaNegocioError, match="máximo permitido"):
        reglas.validar_limite_prestamos(reglas.MAX_PRESTAMOS_ACTIVOS)


@pytest.mark.parametrize(("dias", "mensaje"), [(-1, "posterior"), (reglas.DIAS_MAXIMOS_PRESTAMO + 1, "más de")])
def test_fecha_de_devolucion_invalida(dias, mensaje):
    ahora = datetime.now()
    with pytest.raises(ReglaNegocioError, match=mensaje):
        reglas.validar_fecha_devolucion(ahora, ahora + timedelta(days=dias))


def test_devolucion_solo_disponible_o_danado():
    with pytest.raises(ReglaNegocioError, match="disponible o dañado"):
        reglas.validar_estado_devolucion(EstadoRecurso.prestado)


# --- Servicios con base de datos temporal --------------------------------------------------------


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Redirige todos los repositorios a una base temporal con 2 espacios y 3 equipos."""
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'central.db'}")
    db.crear_tablas(motor)
    from nexo_campus.repositories import catalogo, incidencias, prestamos, reservas

    for modulo in (catalogo, incidencias, prestamos, reservas):
        for nombre in dir(modulo):
            funcion = getattr(modulo, nombre)
            if (
                callable(funcion) and getattr(funcion, "__module__", "") == modulo.__name__
                and "motor_db" in inspect.signature(funcion).parameters
            ):
                monkeypatch.setattr(modulo, nombre, lambda *a, _f=funcion, **k: _f(*a, motor_db=motor, **k))

    with db.obtener_sesion(motor) as sesion:
        sesion.add_all([
            Espacio(id="APOLO", nombre="Apolo", tipo="sala_de_computo", aforo=34),
            Espacio(id="COSMOS", nombre="Cosmos", tipo="sala", aforo=25),
            Recurso(id="PT-01", nombre="Portátil 1", tipo="portatil"),
            Recurso(id="PT-02", nombre="Portátil 2", tipo="portatil"),
            Recurso(id="PT-03", nombre="Portátil 3", tipo="portatil"),
            Recurso(id="APOLO-PC01", nombre="PC de torre 01", tipo="pc_torre", ubicacion="Apolo"),
        ])
        sesion.commit()
    return motor


def estado_espacio(espacio_id):
    from nexo_campus.repositories import reservas

    return reservas.obtener_espacio(espacio_id).estado


def estado_recurso(recurso_id):
    from nexo_campus.repositories import prestamos

    return prestamos.obtener_recurso(recurso_id).estado


def incidencia(prioridad, espacio_id=None, recurso_id=None, texto="Sale humo del tomacorriente"):
    return servicio_incidencias.registrar_incidencia(
        texto, "Ana", espacio_id, recurso_id, "seguridad", prioridad, "seguridad", None, OrigenClasificacion.manual
    )


def test_prestar_y_devolver(base):
    prestamo = servicio.prestar_recurso("PT-01", "  Luis  Gómez ", MANANA)
    assert (prestamo.estado, prestamo.solicitante, estado_recurso("PT-01")) == (EstadoPrestamo.activo, "Luis Gómez", EstadoRecurso.prestado)

    with pytest.raises(ReglaNegocioError, match="'prestado'"):
        servicio.prestar_recurso("PT-01", "Ana", MANANA)

    devuelto = servicio.devolver_recurso(prestamo.id, EstadoRecurso.danado, "Pantalla rota")
    assert devuelto.estado is EstadoPrestamo.devuelto and devuelto.fecha_devolucion is not None
    assert estado_recurso("PT-01") is EstadoRecurso.danado

    from nexo_campus.repositories import prestamos

    assert [(h.estado_nuevo, h.origen) for h in prestamos.listar_historial("PT-01")] == [
        (EstadoRecurso.danado, OrigenCambioEstado.devolucion),
        (EstadoRecurso.prestado, OrigenCambioEstado.prestamo),
    ]
    with pytest.raises(ReglaNegocioError, match="ya fue devuelto"):
        servicio.devolver_recurso(prestamo.id, EstadoRecurso.disponible)


def test_regla5_en_el_servicio(base):
    servicio.prestar_recurso("PT-01", "Luis", MANANA)
    servicio.prestar_recurso("PT-02", "luis ", MANANA)  # misma persona aunque cambien mayúsculas y espacios
    with pytest.raises(ReglaNegocioError, match="2 préstamos activos"):
        servicio.prestar_recurso("PT-03", "Luis", MANANA)


def test_pc_de_torre_no_se_presta(base):
    with pytest.raises(ReglaNegocioError, match="junto con todos los PCs de la sala Apolo"):
        servicio.prestar_recurso("APOLO-PC01", "Luis", MANANA)


def test_incidencia_grave_bloquea_el_espacio_y_al_cerrar_se_libera(base):
    reserva = servicio_reservas.crear_reserva("APOLO", "Ruiz", MANANA, MANANA + timedelta(hours=2), 20)

    grave = incidencia(Prioridad.critica, espacio_id="APOLO")
    assert estado_espacio("APOLO") is EstadoEspacio.inhabilitado
    assert [r.id for r in regla_central.reservas_por_reubicar("APOLO")] == [reserva.id]
    with pytest.raises(ReglaNegocioError, match="inhabilitado"):
        servicio_reservas.crear_reserva("APOLO", "Otra", MANANA + timedelta(hours=3), MANANA + timedelta(hours=4), 10)

    servicio_incidencias.cerrar_incidencia(grave.id)
    assert estado_espacio("APOLO") is EstadoEspacio.disponible
    servicio_reservas.crear_reserva("APOLO", "Otra", MANANA + timedelta(hours=3), MANANA + timedelta(hours=4), 10)


def test_incidencia_media_no_bloquea(base):
    incidencia(Prioridad.media, espacio_id="COSMOS")
    assert estado_espacio("COSMOS") is EstadoEspacio.disponible


def test_se_libera_solo_al_cerrar_la_ultima_incidencia_grave(base):
    primera = incidencia(Prioridad.alta, espacio_id="APOLO")
    segunda = incidencia(Prioridad.critica, espacio_id="APOLO", texto="Huele a quemado")

    servicio_incidencias.cerrar_incidencia(primera.id)
    assert estado_espacio("APOLO") is EstadoEspacio.inhabilitado
    servicio_incidencias.cerrar_incidencia(segunda.id)
    assert estado_espacio("APOLO") is EstadoEspacio.disponible


def test_vuelve_al_estado_que_tenia_antes(base):
    from nexo_campus.services import catalogo

    catalogo.actualizar_espacio("COSMOS", "Cosmos", "sala", 25, None, EstadoEspacio.mantenimiento)
    grave = incidencia(Prioridad.critica, espacio_id="COSMOS")
    assert estado_espacio("COSMOS") is EstadoEspacio.inhabilitado
    servicio_incidencias.cerrar_incidencia(grave.id)
    assert estado_espacio("COSMOS") is EstadoEspacio.mantenimiento


def test_no_libera_lo_que_estaba_inhabilitado_por_otra_razon(base):
    from nexo_campus.services import catalogo

    catalogo.actualizar_espacio("COSMOS", "Cosmos", "sala", 25, None, EstadoEspacio.inhabilitado)
    grave = incidencia(Prioridad.critica, espacio_id="COSMOS")
    servicio_incidencias.cerrar_incidencia(grave.id)
    assert estado_espacio("COSMOS") is EstadoEspacio.inhabilitado


def test_incidencia_grave_bloquea_el_prestamo_de_un_equipo(base):
    grave = incidencia(Prioridad.alta, recurso_id="PT-01", texto="El cargador echa chispas")
    assert estado_recurso("PT-01") is EstadoRecurso.inhabilitado
    with pytest.raises(ReglaNegocioError, match="'inhabilitado'"):
        servicio.prestar_recurso("PT-01", "Luis", MANANA)

    servicio_incidencias.cerrar_incidencia(grave.id)
    assert estado_recurso("PT-01") is EstadoRecurso.disponible
    servicio.prestar_recurso("PT-01", "Luis", MANANA)


def test_equipo_prestado_se_bloquea_al_devolverse(base):
    prestamo = servicio.prestar_recurso("PT-02", "Luis", MANANA)
    grave = incidencia(Prioridad.critica, recurso_id="PT-02", texto="La batería se infló")
    assert estado_recurso("PT-02") is EstadoRecurso.prestado  # no se le quita a quien lo tiene

    servicio.devolver_recurso(prestamo.id, EstadoRecurso.disponible)
    assert estado_recurso("PT-02") is EstadoRecurso.inhabilitado
    servicio_incidencias.cerrar_incidencia(grave.id)
    assert estado_recurso("PT-02") is EstadoRecurso.disponible


# --- PCs que se prestan junto con su sala ---------------------------------------------------------


def test_reservar_la_sala_presta_sus_pcs_operativos(base):
    from nexo_campus.models import Reserva
    from nexo_campus.services import catalogo

    catalogo.crear_recurso("APOLO-PC02", "PC de torre 02", "pc_torre", "apolo")  # la ubicación no distingue mayúsculas
    catalogo.actualizar_recurso("APOLO-PC02", "PC de torre 02", "pc_torre", "apolo", EstadoRecurso.danado, "No enciende")

    pcs = servicio_reservas.pcs_de_la_sala("APOLO")
    assert ([p.id for p in pcs.operativos], [p.id for p in pcs.fuera_de_servicio], pcs.total) == (["APOLO-PC01"], ["APOLO-PC02"], 2)
    assert servicio_reservas.pcs_de_la_sala("COSMOS").total == 0  # sala sin PCs

    futura = servicio_reservas.crear_reserva("APOLO", "Ruiz", MANANA, MANANA + timedelta(hours=2), 20)
    servicio_reservas.crear_reserva("COSMOS", "Ana", MANANA, MANANA + timedelta(hours=1), 5)
    assert [r.id for r, _e, _p in servicio_reservas.prestamos_de_salas()] == [futura.id]  # solo salas con PCs

    ahora = datetime.now()
    with db.obtener_sesion(base) as sesion:
        en_curso = Reserva(espacio_id="APOLO", solicitante="Clase en curso", inicio=ahora - timedelta(minutes=30),
                           fin=ahora + timedelta(minutes=30), asistentes=10)
        sesion.add(en_curso)
        sesion.commit()
        sesion.refresh(en_curso)
    en_uso = servicio_reservas.pcs_en_uso()
    assert list(en_uso) == ["APOLO-PC01"] and en_uso["APOLO-PC01"].id == en_curso.id  # el PC dañado no se presta
