"""Pruebas de la carga de datos con archivos que traen los errores típicos de los datos de origen."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlmodel import select

from nexo_campus import db
from nexo_campus.carga import cargar_datos
from nexo_campus.carga import normalizacion as n
from nexo_campus.errors import NexoCampusError
from nexo_campus.models import (
    Espacio,
    EstadoEspacio,
    EstadoPrestamo,
    EstadoRecurso,
    Incidencia,
    OrigenClasificacion,
    Prestamo,
    Recurso,
    Reserva,
    TipoInconsistencia,
)

ESPACIOS = """codigo,nombre,tipo,capacidad,estado
AU-101,Aula 101,Aula,30,Disponible
AU-102,Aula 102,aula,20,En mantenimiento
CU-01,Cubículo 1,Cubículo,4,
AU-101,Aula repetida,aula,25,disponible
AU-103,,aula,30,disponible
AU-104,Aula 104,aula,-5,disponible
AU-105,Aula 105,aula,30,volando
"""

RECURSOS = {
    "recursos": [
        {"id": "PC-01", "nombre": "Portátil 1", "tipo": "portatil", "estado": "disponible"},
        {"id": "PC-02", "nombre": "Portátil 2", "tipo": "portatil", "estado": "prestado"},
        {"id": "PR-01", "nombre": "Proyector", "tipo": "proyector", "estado": "dañado"},
    ]
}

RESERVAS = """id;espacio_id;solicitante;fecha;hora_inicio;hora_fin;asistentes;estado
R1;AU-101;Ana;2026-10-16;08:00;10:00;25;activa
R2;AU-101;Luis;2026-10-16;09:00;11:00;10;activa
R3;AU-101;Luis;2026-10-16;09:00;11:00;10;cancelada
R4;ZZ-999;Ana;2026-10-16;08:00;09:00;5;
R5;CU-01;Ana;2026-10-16;12:00;11:00;2;
R6;CU-01;Ana;2026-13-45;08:00;09:00;2;
R7;CU-01;Ana;2026-10-16;08:00;09:00;10;
R8;au-102;Ana;16/10/2026;14:00;15:00;5;
"""

PRESTAMOS = """id,id_equipo,prestado_a,fecha_prestamo,fecha_devolucion,estado
P1,PC-01,Ana,2026-10-15 08:00,,activo
P2,PC-01,Luis,2026-10-15 09:00,,activo
P3,XX-1,Ana,2026-10-15 09:00,,activo
P4,PR-01,Ana,2026-10-15 10:00,2026-10-14 10:00,devuelto
P5,PR-01,Ana,2026-10-10 10:00,2026-10-11 10:00,
"""

INCIDENCIAS = """id,descripcion,espacio_id,recurso_id,prioridad,estado
I1,El proyector no enciende,AU-101,PR-01,alta,abierta
I1,El proyector no enciende,AU-101,PR-01,alta,abierta
I2,,AU-101,,,
I3,Fuga de agua,AU-999,,,
"""


@pytest.fixture
def motor(tmp_path: Path):
    return db.crear_motor(f"sqlite:///{tmp_path / 'prueba.db'}")


@pytest.fixture
def datos(tmp_path: Path) -> Path:
    carpeta = tmp_path / "raw"
    carpeta.mkdir()
    (carpeta / "espacios.csv").write_text(ESPACIOS, encoding="utf-8")
    (carpeta / "recursos.json").write_text(json.dumps(RECURSOS), encoding="utf-8")
    (carpeta / "reservas.csv").write_text(RESERVAS, encoding="utf-8")
    (carpeta / "prestamos.csv").write_text(PRESTAMOS, encoding="utf-8")
    (carpeta / "incidencias.csv").write_text(INCIDENCIAS, encoding="utf-8")
    return carpeta


def motivos(reporte, entidad: str, tipo=TipoInconsistencia.rechazado) -> dict[int | None, str]:
    return {i.fila: i.motivo for i in reporte.inconsistencias if i.entidad == entidad and i.tipo is tipo}


def test_resumen_por_entidad(motor, datos):
    reporte = cargar_datos(motor, datos)
    resumen = {r.entidad: (r.leidos, r.cargados, r.rechazados) for r in reporte.resumen}

    assert resumen["espacios"] == (7, 3, 4)
    assert resumen["recursos"] == (3, 3, 0)
    assert resumen["reservas"] == (8, 3, 5)
    assert resumen["prestamos"] == (5, 2, 3)
    assert resumen["incidencias"] == (4, 1, 3)


def test_espacios_invalidos_se_rechazan_con_motivo(motor, datos):
    rechazos = motivos(cargar_datos(motor, datos), "espacios")

    assert "ID duplicado 'AU-101'" in rechazos[5]
    assert "Falta el valor de 'nombre'" in rechazos[6]
    assert "'aforo' debe ser mayor o igual a 1" in rechazos[7]
    assert "Valor no reconocido en 'estado'" in rechazos[8]


def test_espacios_validos_se_normalizan(motor, datos):
    reporte = cargar_datos(motor, datos)
    with db.obtener_sesion(motor) as sesion:
        espacios = {e.id: e for e in sesion.exec(select(Espacio))}

    assert espacios["AU-102"].estado is EstadoEspacio.mantenimiento
    assert espacios["CU-01"].tipo == "cubiculo"
    assert espacios["CU-01"].estado is EstadoEspacio.disponible
    assert "'estado' vacío" in motivos(reporte, "espacios", TipoInconsistencia.advertencia)[4]


def test_reservas_detectan_huerfanos_fechas_aforo_y_solapamientos(motor, datos):
    rechazos = motivos(cargar_datos(motor, datos), "reservas")

    assert "se solapa" in rechazos[3].lower()
    assert "ID huérfano" in rechazos[5]
    assert "no es posterior" in rechazos[6]
    assert "Fecha inválida en 'fecha'" in rechazos[7]
    assert "superan el aforo" in rechazos[8]


def test_reservas_combinan_fecha_y_hora_y_normalizan_ids(motor, datos):
    cargar_datos(motor, datos)
    with db.obtener_sesion(motor) as sesion:
        reservas = {r.codigo_origen: r for r in sesion.exec(select(Reserva))}

    assert reservas["R1"].inicio == datetime(2026, 10, 16, 8, 0)
    assert reservas["R8"].espacio_id == "AU-102"
    assert reservas["R8"].inicio == datetime(2026, 10, 16, 14, 0)
    assert "R3" in reservas  # cancelada: no choca con R1


def test_prestamos_y_conciliacion_de_estado_de_recursos(motor, datos):
    reporte = cargar_datos(motor, datos)
    rechazos = motivos(reporte, "prestamos")

    assert "ya tiene un préstamo activo" in rechazos[3]
    assert "ID huérfano" in rechazos[4]
    assert "anterior a la fecha del préstamo" in rechazos[5]

    with db.obtener_sesion(motor) as sesion:
        recursos = {r.id: r for r in sesion.exec(select(Recurso))}
        p5 = sesion.exec(select(Prestamo).where(Prestamo.codigo_origen == "P5")).one()

    assert recursos["PC-01"].estado is EstadoRecurso.prestado  # tenía préstamo activo
    assert recursos["PC-02"].estado is EstadoRecurso.disponible  # decía prestado sin préstamo
    assert recursos["PR-01"].estado is EstadoRecurso.danado
    assert p5.estado is EstadoPrestamo.devuelto  # deducido por la fecha de devolución


def test_incidencias(motor, datos):
    rechazos = motivos(cargar_datos(motor, datos), "incidencias")

    assert "Fila duplicada" in rechazos[3]
    assert "Falta el valor de 'descripcion'" in rechazos[4]
    assert "ID huérfano" in rechazos[5]

    with db.obtener_sesion(motor) as sesion:
        incidencia = sesion.exec(select(Incidencia)).one()
    assert incidencia.origen_clasificacion is OrigenClasificacion.datos_origen


def test_inconsistencias_quedan_guardadas_en_la_base(motor, datos):
    reporte = cargar_datos(motor, datos)
    from nexo_campus.repositories.catalogo import listar_inconsistencias

    assert len(listar_inconsistencias(motor_db=motor)) == len(reporte.inconsistencias)


def test_archivo_faltante_y_columna_obligatoria_ausente(motor, tmp_path):
    carpeta = tmp_path / "raw"
    carpeta.mkdir()
    (carpeta / "espacios.csv").write_text("id,nombre\nAU-1,Aula 1\n", encoding="utf-8")

    reporte = cargar_datos(motor, carpeta)
    archivo = [i for i in reporte.inconsistencias if i.fila is None]

    assert any(i.entidad == "espacios" and "aforo" in i.motivo for i in archivo)
    assert any(i.entidad == "recursos" and "No se encontró" in i.motivo for i in archivo)


def test_no_borra_datos_sin_reiniciar(motor, datos):
    cargar_datos(motor, datos)
    with pytest.raises(NexoCampusError, match="--reiniciar"):
        cargar_datos(motor, datos)
    assert cargar_datos(motor, datos, reiniciar=True).total_cargados == 12


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("30", 30), ("30.0", 30), (" 4 ", 4)],
)
def test_entero_valido(valor, esperado):
    assert n.entero(valor, "aforo") == esperado


@pytest.mark.parametrize("valor", ["3.5", "treinta", "-1"])
def test_entero_invalido(valor):
    with pytest.raises(n.DatoInvalido):
        n.entero(valor, "aforo", minimo=0)


@pytest.mark.parametrize(
    "valor", ["2026-10-16 08:30", "2026-10-16T08:30:00", "16/10/2026 08:30"]
)
def test_formatos_de_fecha(valor):
    assert n.fecha_hora(valor, "inicio") == datetime(2026, 10, 16, 8, 30)


def test_normalizar_clave():
    assert n.normalizar_clave("  En Mantenimiento ") == "en_mantenimiento"
    assert n.normalizar_clave("Dañado") == "danado"
