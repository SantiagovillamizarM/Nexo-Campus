"""Registro de espacios y recursos desde la app, e importación de archivos oficiales subidos por la página."""

import json
from datetime import datetime, timedelta

import pytest

from nexo_campus import db
from nexo_campus.carga import importacion
from nexo_campus.errors import NexoCampusError, ReglaNegocioError
from nexo_campus.models import (
    Espacio,
    EstadoEspacio,
    EstadoRecurso,
    OrigenCambioEstado,
    Prestamo,
    Recurso,
    Reserva,
)
from nexo_campus.rules import catalogo as reglas
from nexo_campus.services import catalogo as servicio


# --- Reglas --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("entrada", "esperado"), [(" au-101 ", "AU-101"), ("PC001", "PC001")])
def test_codigo_valido(entrada, esperado):
    assert reglas.normalizar_codigo(entrada) == esperado


@pytest.mark.parametrize("codigo", ["", "A", "AU 101", "AU_101", "-AU", "X" * 21])
def test_codigo_invalido(codigo):
    with pytest.raises(ReglaNegocioError, match="código"):
        reglas.normalizar_codigo(codigo)


@pytest.mark.parametrize("aforo", [0, reglas.AFORO_MAXIMO + 1])
def test_aforo_fuera_de_rango(aforo):
    with pytest.raises(ReglaNegocioError, match="aforo"):
        reglas.validar_aforo_espacio(aforo)


def test_no_se_marca_prestado_a_mano():
    with pytest.raises(ReglaNegocioError, match="Prestado"):
        reglas.validar_estado_recurso(EstadoRecurso.prestado, EstadoRecurso.disponible, tiene_prestamo_activo=False)


def test_equipo_prestado_no_cambia_de_estado():
    with pytest.raises(ReglaNegocioError, match="devolución"):
        reglas.validar_estado_recurso(EstadoRecurso.mantenimiento, EstadoRecurso.prestado, tiene_prestamo_activo=True)


# --- Servicio con base de datos real temporal ----------------------------------------------------


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Redirige los repositorios a una base temporal (sus funciones reciben el motor por defecto)."""
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'catalogo.db'}")
    db.crear_tablas(motor)
    from nexo_campus.repositories import catalogo, prestamos, reservas

    for modulo in (catalogo, prestamos, reservas):
        for nombre in dir(modulo):
            funcion = getattr(modulo, nombre)
            if callable(funcion) and getattr(funcion, "__module__", "") == modulo.__name__:
                monkeypatch.setattr(modulo, nombre, lambda *a, _f=funcion, **k: _f(*a, motor_db=motor, **k))
    return motor


def test_crear_y_editar_espacio(base):
    creado = servicio.crear_espacio(" lab-01 ", "Laboratorio 1", "Laboratorio", 25, "Bloque B")
    assert (creado.id, creado.tipo, creado.estado) == ("LAB-01", "laboratorio", EstadoEspacio.disponible)

    with pytest.raises(ReglaNegocioError, match="Ya existe"):
        servicio.crear_espacio("LAB-01", "Otro", "aula", 10)

    editado = servicio.actualizar_espacio("LAB-01", "Laboratorio de redes", "laboratorio", 30, None, EstadoEspacio.mantenimiento)
    assert (editado.nombre, editado.aforo, editado.estado, editado.ubicacion) == ("Laboratorio de redes", 30, EstadoEspacio.mantenimiento, None)


def test_no_baja_aforo_por_debajo_de_una_reserva_futura(base):
    servicio.crear_espacio("AU-1", "Aula 1", "aula", 30)
    manana = datetime.now() + timedelta(days=1)
    with db.obtener_sesion(base) as sesion:
        sesion.add(Reserva(espacio_id="AU-1", solicitante="Ana", inicio=manana, fin=manana + timedelta(hours=1), asistentes=25))
        sesion.commit()

    with pytest.raises(ReglaNegocioError, match="25 personas"):
        servicio.actualizar_espacio("AU-1", "Aula 1", "aula", 20, None, EstadoEspacio.disponible)
    assert servicio.actualizar_espacio("AU-1", "Aula 1", "aula", 25, None, EstadoEspacio.disponible).aforo == 25


def test_cambio_de_estado_de_recurso_queda_en_historial(base):
    servicio.crear_recurso("PC-9", "Portátil 9", "Portátil")
    servicio.actualizar_recurso("PC-9", "Portátil 9", "portatil", None, EstadoRecurso.mantenimiento, "Teclado dañado")

    from nexo_campus.repositories import prestamos

    historial = prestamos.listar_historial("PC-9")
    assert [(h.estado_anterior, h.estado_nuevo, h.origen, h.motivo) for h in historial] == [
        (EstadoRecurso.disponible, EstadoRecurso.mantenimiento, OrigenCambioEstado.edicion, "Teclado dañado")
    ]


def test_recurso_con_prestamo_activo_no_cambia_de_estado(base):
    servicio.crear_recurso("PC-8", "Portátil 8", "portatil")
    with db.obtener_sesion(base) as sesion:
        sesion.add(Prestamo(recurso_id="PC-8", solicitante="Luis", fecha_prestamo=datetime.now()))
        sesion.commit()
    with pytest.raises(ReglaNegocioError, match="préstamo activo"):
        servicio.actualizar_recurso("PC-8", "Portátil 8", "portatil", None, EstadoRecurso.danado)


# --- Importación desde la página -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "entidad"),
    [("Espacios_Campus 2026.xlsx", "espacios"), ("inventario-equipos.csv", "recursos"),
     ("Préstamos.json", "prestamos"), ("datos.csv", None)],
)
def test_adivinar_entidad(nombre, entidad):
    assert importacion.adivinar_entidad(nombre) == entidad


def test_importar_archivos(tmp_path):
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'importacion.db'}")
    carpeta = tmp_path / "raw"
    carpeta.mkdir()
    (carpeta / "espacios.json").write_text("[]", encoding="utf-8")  # versión vieja con otra extensión
    espacios = "codigo,nombre,tipo,capacidad\nAU-1,Aula 1,aula,30\nAU-1,Repetida,aula,20\n".encode()
    recursos = json.dumps([{"id": "PC-1", "nombre": "Portátil", "tipo": "portatil"}]).encode()

    reporte = importacion.importar_archivos(
        {"espacios": ("Espacios Campus.csv", espacios), "recursos": ("equipos.json", recursos)},
        reemplazar=False, directorio=carpeta, motor_db=motor,
    )

    assert sorted(p.name for p in carpeta.iterdir()) == ["espacios.csv", "recursos.json"]
    assert {r.entidad: (r.cargados, r.rechazados) for r in reporte.resumen}["espacios"] == (1, 1)
    with db.obtener_sesion(motor) as sesion:
        assert sesion.get(Espacio, "AU-1") is not None and sesion.get(Recurso, "PC-1") is not None

    with pytest.raises(NexoCampusError, match="reemplazarla"):
        importacion.importar_archivos({"espacios": ("e.csv", espacios)}, reemplazar=False, directorio=carpeta, motor_db=motor)


@pytest.mark.parametrize(
    ("archivos", "mensaje"),
    [({}, "al menos un archivo"), ({"espacios": ("e.txt", b"x")}, "formato"), ({"espacios": ("e.csv", b"")}, "vacío")],
)
def test_importar_valida_antes_de_escribir(tmp_path, archivos, mensaje):
    motor = db.crear_motor(f"sqlite:///{tmp_path / 'x.db'}")
    with pytest.raises(NexoCampusError, match=mensaje):
        importacion.importar_archivos(archivos, reemplazar=True, directorio=tmp_path / "raw", motor_db=motor)
    assert not (tmp_path / "raw").exists()
