"""Registro y edición de espacios y recursos: la pantalla de administración llama a estas funciones."""

from datetime import datetime

from nexo_campus.carga.normalizacion import normalizar_clave
from nexo_campus.models import Espacio, EstadoEspacio, EstadoRecurso, EstadoReserva, OrigenCambioEstado, Recurso
from nexo_campus.repositories import catalogo as repositorio
from nexo_campus.repositories import prestamos as repositorio_prestamos
from nexo_campus.repositories import reservas as repositorio_reservas
from nexo_campus.rules import catalogo as reglas
from nexo_campus.errors import ReglaNegocioError


def _tipo(tipo: str) -> str:
    # Mismo formato que la carga de datos ("Cubículo" -> "cubiculo"), para que los filtros coincidan.
    return normalizar_clave(reglas.validar_texto_obligatorio(tipo, "tipo"))


def _opcional(valor: str | None) -> str | None:
    return " ".join((valor or "").split()) or None


# --- Espacios ------------------------------------------------------------------------------------


def crear_espacio(
    codigo: str, nombre: str, tipo: str, aforo: int, ubicacion: str | None = None,
    estado: EstadoEspacio = EstadoEspacio.disponible,
) -> Espacio:
    codigo = reglas.normalizar_codigo(codigo)
    reglas.validar_codigo_libre(codigo, repositorio_reservas.obtener_espacio(codigo) is not None, "espacio")
    reglas.validar_aforo_espacio(aforo)
    espacio = Espacio(
        id=codigo,
        nombre=reglas.validar_texto_obligatorio(nombre, "nombre"),
        tipo=_tipo(tipo),
        aforo=aforo,
        ubicacion=_opcional(ubicacion),
        estado=estado,
    )
    return repositorio.guardar_espacio(espacio)


def actualizar_espacio(
    espacio_id: str, nombre: str, tipo: str, aforo: int, ubicacion: str | None, estado: EstadoEspacio
) -> Espacio:
    espacio = repositorio_reservas.obtener_espacio(espacio_id)
    if espacio is None:
        raise ReglaNegocioError(f"No existe un espacio con el código '{espacio_id}'.")
    reglas.validar_aforo_espacio(aforo)
    futuras = [
        r for r in repositorio_reservas.listar_reservas(espacio_id=espacio_id, desde=datetime.now())
        if r.estado is EstadoReserva.activa
    ]
    reglas.validar_aforo_frente_a_reservas(aforo, max((r.asistentes for r in futuras), default=0))

    espacio.nombre = reglas.validar_texto_obligatorio(nombre, "nombre")
    espacio.tipo = _tipo(tipo)
    espacio.aforo = aforo
    espacio.ubicacion = _opcional(ubicacion)
    repositorio.guardar_espacio(espacio)  # el estado se mantiene: el cambio va con historial
    return repositorio.cambiar_estado_espacio(espacio_id, estado, "Cambio desde administración", OrigenCambioEstado.edicion)


# --- Recursos ------------------------------------------------------------------------------------


def crear_recurso(
    codigo: str, nombre: str, tipo: str, ubicacion: str | None = None,
    estado: EstadoRecurso = EstadoRecurso.disponible,
) -> Recurso:
    codigo = reglas.normalizar_codigo(codigo)
    reglas.validar_codigo_libre(codigo, repositorio_prestamos.obtener_recurso(codigo) is not None, "recurso")
    reglas.validar_estado_recurso(estado, actual=None, tiene_prestamo_activo=False)
    recurso = Recurso(
        id=codigo,
        nombre=reglas.validar_texto_obligatorio(nombre, "nombre"),
        tipo=_tipo(tipo),
        ubicacion=_opcional(ubicacion),
        estado=estado,
    )
    return repositorio.guardar_recurso(recurso)


def actualizar_recurso(
    recurso_id: str, nombre: str, tipo: str, ubicacion: str | None, estado: EstadoRecurso, motivo: str | None = None
) -> Recurso:
    """Actualiza los datos del equipo. Si cambia el estado, queda registrado en el historial."""
    recurso = repositorio_prestamos.obtener_recurso(recurso_id)
    if recurso is None:
        raise ReglaNegocioError(f"No existe un recurso con el código '{recurso_id}'.")
    tiene_prestamo = repositorio_prestamos.prestamo_activo_de_recurso(recurso_id) is not None
    reglas.validar_estado_recurso(estado, actual=recurso.estado, tiene_prestamo_activo=tiene_prestamo)

    recurso.nombre = reglas.validar_texto_obligatorio(nombre, "nombre")
    recurso.tipo = _tipo(tipo)
    recurso.ubicacion = _opcional(ubicacion)
    repositorio.guardar_recurso(recurso)  # el estado se mantiene: el cambio va con historial
    return repositorio_prestamos.cambiar_estado_recurso(
        recurso_id, estado, _opcional(motivo) or "Cambio desde administración", OrigenCambioEstado.edicion
    )
