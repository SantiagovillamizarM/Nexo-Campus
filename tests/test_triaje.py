"""Pruebas de la validación del triaje. No llaman a la IA: revisan qué respuestas se aceptan."""

import pytest
from pydantic import ValidationError

from nexo_campus.ai.triaje import Triaje, clasificar_incidencia
from nexo_campus.errors import NexoCampusError
from nexo_campus.models import Prioridad


def _respuesta(**cambios: str) -> dict[str, str]:
    base = {
        "categoria": "tecnologia",
        "prioridad": "alta",
        "area_responsable": "soporte_ti",
        "justificacion": "El proyector no enciende y impide dar la clase.",
    }
    return base | cambios


def test_acepta_respuesta_valida():
    triaje = Triaje.model_validate(_respuesta())
    assert triaje.categoria == "tecnologia"
    assert triaje.prioridad == Prioridad.alta


def test_normaliza_tildes_y_mayusculas():
    triaje = Triaje.model_validate(
        _respuesta(categoria="Tecnología", prioridad="ALTA", area_responsable="Soporte TI")
    )
    assert triaje.categoria == "tecnologia"
    assert triaje.prioridad == Prioridad.alta
    assert triaje.area_responsable == "soporte_ti"


@pytest.mark.parametrize(
    "cambio",
    [
        {"categoria": "otro"},
        {"prioridad": "urgente"},
        {"area_responsable": "rectoria"},
        {"justificacion": "   "},
        {"area_responsable": "mantenimiento"},  # existe, pero no corresponde a tecnologia
    ],
)
def test_rechaza_respuesta_fuera_de_las_reglas(cambio):
    with pytest.raises(ValidationError):
        Triaje.model_validate(_respuesta(**cambio))


@pytest.mark.parametrize("texto", ["", "   ", "x" * 1001])
def test_rechaza_texto_vacio_o_demasiado_largo_sin_llamar_a_la_ia(texto):
    with pytest.raises(NexoCampusError):
        clasificar_incidencia(texto)
