"""Servicio de incidencias probado con repositorios en memoria y la IA reemplazada.

RepositorioEnMemoria implementa las funciones del contrato de P1 que usa el servicio
(repositories/incidencias.py y obtener_recurso de repositories/prestamos.py).
"""

import importlib.util
import sys
import types
from datetime import datetime

import pytest

# Mientras no existan los repositorios reales, se registra un módulo vacío para poder importar el
# servicio. Las pruebas reemplazan los repositorios por los de memoria en cualquier caso.
for _modulo in ("nexo_campus.repositories.incidencias", "nexo_campus.repositories.prestamos"):
    if importlib.util.find_spec(_modulo) is None:
        sys.modules[_modulo] = types.ModuleType(_modulo)

from nexo_campus.ai.triaje import Triaje  # noqa: E402
from nexo_campus.errors import IAError, ReglaNegocioError  # noqa: E402
from nexo_campus.models import (  # noqa: E402
    Espacio,
    EstadoIncidencia,
    Incidencia,
    OrigenClasificacion,
    Prioridad,
    Recurso,
    Reserva,
)
from nexo_campus.services import incidencias as servicio  # noqa: E402


class RepositorioEnMemoria:
    def __init__(self):
        self.espacios = {"AU-201": Espacio(id="AU-201", nombre="Aula Turing", tipo="aula", aforo=30)}
        self.recursos = {"PRY-02": Recurso(id="PRY-02", nombre="Video beam", tipo="proyector")}
        self.reservas_en_curso: list[Reserva] = []
        self.incidencias: dict[int, Incidencia] = {}

    # reservas (P1, ya existe)
    def obtener_espacio(self, espacio_id):
        return self.espacios.get(espacio_id)

    def reservas_activas_en_franja(self, espacio_id, inicio, fin, excluir_id=None):
        return [r for r in self.reservas_en_curso if r.espacio_id == espacio_id]

    # prestamos (P1)
    def obtener_recurso(self, recurso_id):
        return self.recursos.get(recurso_id)

    # incidencias (P1)
    def guardar_incidencia(self, incidencia):
        if incidencia.id is None:
            incidencia.id = len(self.incidencias) + 1
        self.incidencias[incidencia.id] = incidencia
        return incidencia

    def obtener_incidencia(self, incidencia_id):
        return self.incidencias.get(incidencia_id)

    def cerrar_incidencia(self, incidencia_id):
        incidencia = self.incidencias[incidencia_id]
        incidencia.estado = EstadoIncidencia.cerrada
        incidencia.fecha_cierre = datetime.now()
        return incidencia


PROPUESTA = Triaje(
    categoria="tecnologia", prioridad=Prioridad.alta, area_responsable="soporte_ti", justificacion="No enciende."
)


class ReglaCentralFalsa:
    """Registra las llamadas a la regla central (P2), que tiene sus propias pruebas con base de datos."""

    def __init__(self):
        self.bloqueadas: list[int] = []
        self.liberadas: list[int] = []

    def bloquear_por_incidencia(self, incidencia):
        self.bloqueadas.append(incidencia.id)

    def liberar_por_cierre(self, incidencia):
        self.liberadas.append(incidencia.id)
        return []


@pytest.fixture
def repo(monkeypatch):
    repositorio = RepositorioEnMemoria()
    repositorio.regla_central = ReglaCentralFalsa()
    monkeypatch.setattr(servicio, "repositorio_reservas", repositorio)
    monkeypatch.setattr(servicio, "repositorio_prestamos", repositorio)
    monkeypatch.setattr(servicio, "repositorio_incidencias", repositorio)
    monkeypatch.setattr(servicio, "regla_central", repositorio.regla_central)
    return repositorio


@pytest.fixture
def ia(monkeypatch):
    llamadas = []

    def clasificar_falso(texto, espacio=None, recurso=None, reserva_en_curso=None):
        llamadas.append({"texto": texto, "espacio": espacio, "recurso": recurso, "reserva": reserva_en_curso})
        return PROPUESTA

    monkeypatch.setattr(servicio, "clasificar_incidencia", clasificar_falso)
    return llamadas


def _registrar(**cambios):
    datos = dict(
        descripcion="El video beam no prende",
        reportante="  Ana   Pérez ",
        espacio_id="AU-201",
        recurso_id="PRY-02",
        categoria="tecnologia",
        prioridad="alta",
        area_responsable="soporte_ti",
        justificacion="No enciende.",
        origen="ia",
    )
    return servicio.registrar_incidencia(**(datos | cambios))


# --- analizar_incidencia ---


def test_analizar_pasa_espacio_recurso_y_clase_en_curso_a_la_ia(repo, ia):
    clase = Reserva(espacio_id="AU-201", solicitante="Prof", asistentes=25,
                    inicio=datetime(2030, 1, 1, 8), fin=datetime(2030, 1, 1, 10))
    repo.reservas_en_curso.append(clase)

    resultado = servicio.analizar_incidencia("  No prende  ", espacio_id="AU-201", recurso_id="PRY-02")

    assert resultado is PROPUESTA
    assert ia[0]["texto"] == "No prende"
    assert ia[0]["espacio"].id == "AU-201" and ia[0]["recurso"].id == "PRY-02"
    assert ia[0]["reserva"] is clase


def test_analizar_no_guarda_nada(repo, ia):
    servicio.analizar_incidencia("No prende", espacio_id="AU-201")
    assert repo.incidencias == {}


@pytest.mark.parametrize(
    "argumentos",
    [{"descripcion": "   "}, {"descripcion": "x", "espacio_id": "NO-EXISTE"}, {"descripcion": "x", "recurso_id": "NO-EXISTE"}],
)
def test_analizar_valida_antes_de_llamar_a_la_ia(repo, ia, argumentos):
    with pytest.raises(ReglaNegocioError):
        servicio.analizar_incidencia(**argumentos)
    assert ia == []


def test_analizar_deja_pasar_el_error_de_la_ia(repo, monkeypatch):
    def ia_caida(*_, **__):
        raise IAError("No se pudo conectar con el servicio de IA.")

    monkeypatch.setattr(servicio, "clasificar_incidencia", ia_caida)
    with pytest.raises(IAError):
        servicio.analizar_incidencia("No prende")


# --- origen_segun_propuesta ---


def test_origen_es_ia_si_se_acepta_la_propuesta_tal_cual():
    assert servicio.origen_segun_propuesta(PROPUESTA, "Tecnología", Prioridad.alta, "soporte_ti") is OrigenClasificacion.ia


def test_origen_es_manual_si_se_corrige_algo_o_no_hubo_propuesta():
    assert servicio.origen_segun_propuesta(PROPUESTA, "tecnologia", "critica", "soporte_ti") is OrigenClasificacion.manual
    assert servicio.origen_segun_propuesta(None, "tecnologia", "alta", "soporte_ti") is OrigenClasificacion.manual


# --- registrar_incidencia ---


def test_registrar_guarda_la_incidencia_abierta(repo):
    incidencia = _registrar(categoria="Tecnología", prioridad="ALTA")

    assert incidencia.id == 1
    assert incidencia.estado is EstadoIncidencia.abierta
    assert incidencia.reportante == "Ana Pérez"
    assert incidencia.categoria == "tecnologia"
    assert incidencia.prioridad is Prioridad.alta
    assert incidencia.origen_clasificacion is OrigenClasificacion.ia
    assert incidencia.fecha_reporte is not None


def test_registrar_manual_acepta_combinacion_corregida_y_sin_justificacion(repo):
    incidencia = _registrar(categoria="seguridad", area_responsable="mantenimiento", justificacion="", origen="manual")
    assert incidencia.origen_clasificacion is OrigenClasificacion.manual
    assert incidencia.justificacion is None


@pytest.mark.parametrize(
    "cambio",
    [
        {"categoria": "electricidad"},
        {"prioridad": "urgente"},
        {"area_responsable": "rectoria"},
        {"descripcion": "  "},
        {"espacio_id": "NO-EXISTE"},
        {"recurso_id": "NO-EXISTE"},
        {"origen": "datos_origen"},  # solo la carga de datos usa este origen
        {"origen": "xyz"},
    ],
)
def test_registrar_rechaza_datos_invalidos_sin_guardar(repo, cambio):
    with pytest.raises(ReglaNegocioError):
        _registrar(**cambio)
    assert repo.incidencias == {}


# --- cerrar_incidencia ---


def test_cerrar_incidencia(repo):
    _registrar()
    cerrada = servicio.cerrar_incidencia(1)
    assert cerrada.estado is EstadoIncidencia.cerrada
    assert cerrada.fecha_cierre is not None


def test_no_se_cierra_dos_veces_ni_una_que_no_existe(repo):
    _registrar()
    servicio.cerrar_incidencia(1)
    with pytest.raises(ReglaNegocioError, match="ya está cerrada"):
        servicio.cerrar_incidencia(1)
    with pytest.raises(ReglaNegocioError, match="No existe"):
        servicio.cerrar_incidencia(99)


def test_registrar_y_cerrar_aplican_la_regla_central(repo):
    incidencia = servicio.registrar_incidencia(
        "Sale humo del proyector", "Ana", "AU-201", "PRY-02",
        "seguridad", Prioridad.critica, "seguridad", None, OrigenClasificacion.manual,
    )
    assert repo.regla_central.bloqueadas == [incidencia.id]

    servicio.cerrar_incidencia(incidencia.id)
    assert repo.regla_central.liberadas == [incidencia.id]
