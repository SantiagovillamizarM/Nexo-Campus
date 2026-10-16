"""Pruebas de las recomendaciones. La IA se reemplaza con monkeypatch: solo se prueba el control de respuestas."""

import pytest

from nexo_campus.ai import recomendaciones
from nexo_campus.ai.recomendaciones import MAX_RECOMENDACIONES, recomendar_espacios
from nexo_campus.errors import IAError
from nexo_campus.models import Espacio

CANDIDATOS = [
    Espacio(id="CU-01", nombre="Cubículo 1", tipo="cubiculo", aforo=4),
    Espacio(id="AU-101", nombre="Aula 101", tipo="aula", aforo=25),
    Espacio(id="AU-201", nombre="Aula 201", tipo="aula", aforo=35),
    Espacio(id="LAB-01", nombre="Laboratorio", tipo="laboratorio", aforo=30),
]


def _ia_recomienda(monkeypatch, *items: tuple[str, int]) -> None:
    def consultar_falso(mensaje, instrucciones, modelo):
        return modelo.model_validate(
            {"recomendaciones": [{"espacio_id": i, "razon": f"razón {i}", "orden": o} for i, o in items]}
        )

    monkeypatch.setattr(recomendaciones, "consultar_json", consultar_falso)


def test_devuelve_las_recomendaciones_en_orden(monkeypatch):
    _ia_recomienda(monkeypatch, ("AU-201", 2), ("AU-101", 1))
    resultado = recomendar_espacios("Clase", 20, CANDIDATOS)
    assert [(r.orden, r.espacio_id) for r in resultado] == [(1, "AU-101"), (2, "AU-201")]


def test_descarta_espacios_inventados_y_repetidos_y_renumera(monkeypatch):
    _ia_recomienda(monkeypatch, ("AU-999", 1), ("AU-101", 2), ("AU-101", 3), ("LAB-01", 4))
    resultado = recomendar_espacios("Clase", 20, CANDIDATOS)
    assert [(r.orden, r.espacio_id) for r in resultado] == [(1, "AU-101"), (2, "LAB-01")]


def test_no_devuelve_mas_del_maximo(monkeypatch):
    _ia_recomienda(monkeypatch, *[(e.id, n) for n, e in enumerate(CANDIDATOS, start=1)])
    assert len(recomendar_espacios("Clase", 2, CANDIDATOS)) == MAX_RECOMENDACIONES


def test_si_todo_es_inventado_lanza_iaerror(monkeypatch):
    _ia_recomienda(monkeypatch, ("AU-999", 1), ("XX-1", 2))
    with pytest.raises(IAError):
        recomendar_espacios("Clase", 20, CANDIDATOS)


def test_sin_candidatos_no_llama_a_la_ia(monkeypatch):
    monkeypatch.setattr(recomendaciones, "consultar_json", lambda *a: pytest.fail("no debía llamar a la IA"))
    assert recomendar_espacios("Clase", 20, []) == []


def test_el_error_de_la_ia_llega_a_quien_llama(monkeypatch):
    def ia_caida(*_):
        raise IAError("No se pudo conectar con el servicio de IA.")

    monkeypatch.setattr(recomendaciones, "consultar_json", ia_caida)
    with pytest.raises(IAError):
        recomendar_espacios("Clase", 20, CANDIDATOS)


def test_el_prompt_solo_incluye_los_candidatos(monkeypatch):
    enviados = []

    def consultar_falso(mensaje, instrucciones, modelo):
        enviados.append(mensaje)
        return modelo.model_validate({"recomendaciones": [{"espacio_id": "CU-01", "razon": "x", "orden": 1}]})

    monkeypatch.setattr(recomendaciones, "consultar_json", consultar_falso)
    recomendar_espacios("Asesoría", 2, CANDIDATOS[:1])
    assert "CU-01" in enviados[0] and "AU-101" not in enviados[0]
