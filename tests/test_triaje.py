"""Pruebas del triaje. No llaman a Ollama: reemplazan la IA con monkeypatch para probar la validación.

Esto solo se hace en las pruebas. En la aplicación la IA nunca se simula.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from nexo_campus import config
from nexo_campus.ai import cliente, triaje
from nexo_campus.ai.triaje import Triaje, clasificar_incidencia
from nexo_campus.errors import IAError, NexoCampusError
from nexo_campus.models import Espacio, Prioridad, Recurso, Reserva


def _respuesta(**cambios: str) -> dict[str, str]:
    base = {
        "categoria": "tecnologia",
        "prioridad": "alta",
        "area_responsable": "soporte_ti",
        "justificacion": "El proyector no enciende y impide dar la clase.",
    }
    return base | cambios


def _ia_responde(monkeypatch, texto_json: str) -> None:
    """Hace que el cliente reciba texto_json como si viniera de la IA."""
    monkeypatch.setattr(cliente, "_completar", lambda mensajes, formato_json: texto_json)


# --- Validación del modelo Triaje ---


def test_acepta_respuesta_valida():
    resultado = Triaje.model_validate(_respuesta())
    assert resultado.categoria == "tecnologia"
    assert resultado.prioridad == Prioridad.alta


def test_normaliza_tildes_y_mayusculas():
    resultado = Triaje.model_validate(
        _respuesta(categoria="Tecnología", prioridad="ALTA", area_responsable="Soporte TI")
    )
    assert resultado.categoria == "tecnologia"
    assert resultado.prioridad == Prioridad.alta
    assert resultado.area_responsable == "soporte_ti"


def test_categoria_otro_acepta_cualquier_area_de_la_lista():
    resultado = Triaje.model_validate(_respuesta(categoria="otro", area_responsable="servicios_generales"))
    assert resultado.categoria == "otro"


@pytest.mark.parametrize(
    "cambio",
    [
        {"categoria": "electricidad"},
        {"prioridad": "urgente"},
        {"area_responsable": "rectoria"},
        {"justificacion": "   "},
        {"area_responsable": "mantenimiento"},  # existe, pero no corresponde a tecnologia
    ],
)
def test_rechaza_respuesta_fuera_de_las_reglas(cambio):
    with pytest.raises(ValidationError):
        Triaje.model_validate(_respuesta(**cambio))


# --- clasificar_incidencia con la IA reemplazada ---


@pytest.mark.parametrize("texto", ["", "   ", "x" * 1001])
def test_rechaza_texto_vacio_o_demasiado_largo_sin_llamar_a_la_ia(monkeypatch, texto):
    monkeypatch.setattr(triaje, "consultar_json", lambda *a: pytest.fail("no debía llamar a la IA"))
    with pytest.raises(NexoCampusError):
        clasificar_incidencia(texto)


def test_devuelve_el_triaje_cuando_la_ia_responde_bien(monkeypatch):
    _ia_responde(monkeypatch, '{"categoria": "Tecnología", "prioridad": "alta", '
                 '"area_responsable": "soporte_ti", "justificacion": "No enciende."}')
    resultado = clasificar_incidencia("El proyector no enciende")
    assert resultado.categoria == "tecnologia"
    assert resultado.prioridad is Prioridad.alta


@pytest.mark.parametrize(
    "texto_json",
    [
        "{esto no es json",
        '{"categoria": "electricidad", "prioridad": "alta", "area_responsable": "soporte_ti", "justificacion": "x"}',
        '{"categoria": "tecnologia", "prioridad": "alta"}',  # faltan campos
    ],
)
def test_respuesta_invalida_de_la_ia_es_iaerror(monkeypatch, texto_json):
    _ia_responde(monkeypatch, texto_json)
    with pytest.raises(IAError):
        clasificar_incidencia("El proyector no enciende")


def test_ia_caida_es_iaerror_con_mensaje_claro(monkeypatch):
    # Puerto cerrado: el cliente real falla al conectarse, igual que con Ollama apagado.
    monkeypatch.setattr(config, "AI_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(config, "AI_MODEL", "modelo-de-prueba")
    with pytest.raises(IAError, match="No se pudo conectar"):
        clasificar_incidencia("El proyector no enciende")


def test_envia_el_contexto_del_espacio_recurso_y_clase_en_curso(monkeypatch):
    enviados = []

    def consultar_falso(mensaje, instrucciones, modelo):
        enviados.append(mensaje)
        return modelo.model_validate(_respuesta(prioridad="critica"))

    monkeypatch.setattr(triaje, "consultar_json", consultar_falso)
    clasificar_incidencia(
        "No prende",
        espacio=Espacio(id="AU-201", nombre="Aula Turing", tipo="aula", aforo=30),
        recurso=Recurso(id="PRY-02", nombre="Video beam", tipo="proyector"),
        reserva_en_curso=Reserva(
            espacio_id="AU-201", solicitante="Prof", asistentes=25,
            inicio=datetime(2030, 1, 1, 8), fin=datetime(2030, 1, 1, 10),
        ),
    )
    assert "Aula Turing (AU-201)" in enviados[0]
    assert "tipo proyector" in enviados[0]
    assert "clase en curso ahora: de 08:00 a 10:00" in enviados[0]
