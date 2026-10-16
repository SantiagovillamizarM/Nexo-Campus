"""Reglas de reservas: un caso válido y casos inválidos por cada regla."""

from datetime import datetime

import pytest

from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import Espacio, EstadoEspacio, Reserva
from nexo_campus.rules import reservas as reglas


def hora(h: int, m: int = 0, dia: int = 15) -> datetime:
    return datetime(2030, 1, dia, h, m)


def espacio(estado: EstadoEspacio = EstadoEspacio.disponible) -> Espacio:
    return Espacio(id="AU-101", nombre="Aula 101", tipo="aula", aforo=30, estado=estado)


# --- Solapamiento --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ((8, 10), (9, 11), True),  # se cruzan
        ((8, 12), (9, 10), True),  # una dentro de la otra
        ((8, 10), (10, 12), False),  # contiguas: una termina cuando empieza la otra
        ((8, 10), (11, 12), False),  # separadas
    ],
)
def test_se_solapan(a, b, esperado):
    assert reglas.se_solapan(hora(a[0]), hora(a[1]), hora(b[0]), hora(b[1])) is esperado


def test_sin_solapamiento_valido():
    reglas.validar_sin_solapamiento([])


def test_con_solapamiento_explica_con_que_choca():
    otra = Reserva(espacio_id="AU-101", solicitante="Ana", inicio=hora(8), fin=hora(10), asistentes=5)
    with pytest.raises(ReglaNegocioError, match="de 08:00 a 10:00 por Ana"):
        reglas.validar_sin_solapamiento([otra])


# --- Aforo ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("asistentes", [1, 30])
def test_aforo_valido(asistentes):
    reglas.validar_aforo(asistentes, aforo=30)


def test_aforo_superado():
    with pytest.raises(ReglaNegocioError, match="aforo de 30 personas y la reserva es para 31"):
        reglas.validar_aforo(31, aforo=30)


def test_aforo_sin_asistentes():
    with pytest.raises(ReglaNegocioError, match="al menos 1 asistente"):
        reglas.validar_aforo(0, aforo=30)


# --- Espacio habilitado --------------------------------------------------------------------------


def test_espacio_disponible_se_puede_reservar():
    reglas.validar_espacio_habilitado(espacio())


@pytest.mark.parametrize("estado", [EstadoEspacio.mantenimiento, EstadoEspacio.inhabilitado])
def test_espacio_no_habilitado(estado):
    with pytest.raises(ReglaNegocioError, match=f"estado '{estado.value}'"):
        reglas.validar_espacio_habilitado(espacio(estado))


# --- Horario -------------------------------------------------------------------------------------


def test_horario_valido():
    reglas.validar_horario(hora(8), hora(10), ahora=hora(7))


@pytest.mark.parametrize(
    ("inicio", "fin", "mensaje"),
    [
        (hora(10), hora(8), "posterior a la hora de inicio"),
        (hora(10), hora(10), "posterior a la hora de inicio"),
        (hora(20), hora(1, dia=16), "mismo día"),
        (hora(5), hora(7), "entre las 06:00 y las 22:00"),
        (hora(21), hora(23), "entre las 06:00 y las 22:00"),
        (hora(8), hora(8, 15), "al menos 30 minutos"),
        (hora(8), hora(13), "más de 4 horas"),
    ],
)
def test_horario_invalido(inicio, fin, mensaje):
    with pytest.raises(ReglaNegocioError, match=mensaje):
        reglas.validar_horario(inicio, fin)


def test_horario_en_el_pasado():
    with pytest.raises(ReglaNegocioError, match="pasado"):
        reglas.validar_horario(hora(8), hora(10), ahora=hora(9))
