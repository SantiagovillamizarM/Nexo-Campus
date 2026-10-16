"""Casos de uso de las incidencias: la UI llama a estas funciones.

El flujo tiene dos pasos para que la persona confirme o corrija lo que propone la IA:
1. analizar_incidencia: valida los datos y pide el triaje a la IA. No guarda nada.
2. registrar_incidencia: guarda la clasificación final, marcando si la hizo la IA o una persona.

Si la IA falla, analizar_incidencia deja pasar el IAError: la UI lo muestra y ofrece clasificar a mano.
Nunca se devuelve una clasificación inventada.
"""

from datetime import datetime, timedelta

from nexo_campus.ai.triaje import AREAS, CATEGORIAS, Triaje, clasificar_incidencia, normalizar_opcion
from nexo_campus.errors import ReglaNegocioError
from nexo_campus.models import (
    Espacio,
    EstadoIncidencia,
    Incidencia,
    OrigenClasificacion,
    Prioridad,
    Recurso,
    Reserva,
)
from nexo_campus.repositories import incidencias as repositorio_incidencias
from nexo_campus.repositories import prestamos as repositorio_prestamos
from nexo_campus.repositories import reservas as repositorio_reservas
from nexo_campus.services import regla_central

ORIGENES_PERMITIDOS = {OrigenClasificacion.ia, OrigenClasificacion.manual}


def _limpiar_descripcion(descripcion: str) -> str:
    limpia = (descripcion or "").strip()
    if not limpia:
        raise ReglaNegocioError("Describe la incidencia antes de continuar.")
    return limpia


def _obtener_espacio(espacio_id: str | None) -> Espacio | None:
    if not espacio_id:
        return None
    espacio = repositorio_reservas.obtener_espacio(espacio_id)
    if espacio is None:
        raise ReglaNegocioError(f"No existe un espacio con el código '{espacio_id}'.")
    return espacio


def _obtener_recurso(recurso_id: str | None) -> Recurso | None:
    if not recurso_id:
        return None
    recurso = repositorio_prestamos.obtener_recurso(recurso_id)
    if recurso is None:
        raise ReglaNegocioError(f"No existe un equipo con el código '{recurso_id}'.")
    return recurso


def _reserva_en_curso(espacio: Espacio | None, ahora: datetime) -> Reserva | None:
    """La reserva activa del espacio en este momento, si la hay. Sube la prioridad del triaje."""
    if espacio is None:
        return None
    activas = repositorio_reservas.reservas_activas_en_franja(espacio.id, ahora, ahora + timedelta(minutes=1))
    return activas[0] if activas else None


def analizar_incidencia(
    descripcion: str, espacio_id: str | None = None, recurso_id: str | None = None
) -> Triaje:
    """Paso 1: propone una clasificación con IA. No guarda nada. Lanza IAError si la IA falla."""
    texto = _limpiar_descripcion(descripcion)
    espacio = _obtener_espacio(espacio_id)
    recurso = _obtener_recurso(recurso_id)
    return clasificar_incidencia(
        texto,
        espacio=espacio,
        recurso=recurso,
        reserva_en_curso=_reserva_en_curso(espacio, datetime.now()),
    )


def origen_segun_propuesta(
    propuesta: Triaje | None, categoria: str, prioridad: Prioridad | str, area_responsable: str
) -> OrigenClasificacion:
    """ia si la persona aceptó la propuesta tal cual; manual si la corrigió o si no hubo propuesta."""
    if propuesta is None:
        return OrigenClasificacion.manual
    sin_cambios = (
        normalizar_opcion(categoria) == propuesta.categoria
        and normalizar_opcion(str(getattr(prioridad, "value", prioridad))) == propuesta.prioridad.value
        and normalizar_opcion(area_responsable) == propuesta.area_responsable
    )
    return OrigenClasificacion.ia if sin_cambios else OrigenClasificacion.manual


def _validar_opcion(valor: str, permitidos: list[str], nombre: str) -> str:
    normalizado = normalizar_opcion(valor or "")
    if normalizado not in permitidos:
        raise ReglaNegocioError(f"La {nombre} '{valor}' no es válida. Opciones: {', '.join(permitidos)}.")
    return normalizado


def _validar_prioridad(prioridad: Prioridad | str) -> Prioridad:
    if isinstance(prioridad, Prioridad):
        return prioridad
    try:
        return Prioridad(normalizar_opcion(prioridad or ""))
    except ValueError as exc:
        opciones = ", ".join(p.value for p in Prioridad)
        raise ReglaNegocioError(f"La prioridad '{prioridad}' no es válida. Opciones: {opciones}.") from exc


def registrar_incidencia(
    descripcion: str,
    reportante: str | None,
    espacio_id: str | None,
    recurso_id: str | None,
    categoria: str,
    prioridad: Prioridad | str,
    area_responsable: str,
    justificacion: str | None,
    origen: OrigenClasificacion | str,
) -> Incidencia:
    """Paso 2: guarda la incidencia con la clasificación que confirmó o corrigió la persona."""
    if origen not in {o.value for o in ORIGENES_PERMITIDOS} | ORIGENES_PERMITIDOS:
        raise ReglaNegocioError("El origen de la clasificación debe ser 'ia' o 'manual'.")
    origen = OrigenClasificacion(origen)

    espacio = _obtener_espacio(espacio_id)
    recurso = _obtener_recurso(recurso_id)
    incidencia = Incidencia(
        descripcion=_limpiar_descripcion(descripcion),
        reportante=" ".join((reportante or "").split()) or None,
        espacio_id=espacio.id if espacio else None,
        recurso_id=recurso.id if recurso else None,
        fecha_reporte=datetime.now(),
        categoria=_validar_opcion(categoria, CATEGORIAS, "categoría"),
        prioridad=_validar_prioridad(prioridad),
        area_responsable=_validar_opcion(area_responsable, AREAS, "área responsable"),
        justificacion=(justificacion or "").strip() or None,
        origen_clasificacion=origen,
        estado=EstadoIncidencia.abierta,
    )
    guardada = repositorio_incidencias.guardar_incidencia(incidencia)
    regla_central.bloquear_por_incidencia(guardada)  # si es grave, inhabilita el espacio o equipo
    return guardada


def cerrar_incidencia(incidencia_id: int) -> Incidencia:
    """Cierra la incidencia y, por la regla central, libera el espacio o equipo que mantenía bloqueado."""
    incidencia = repositorio_incidencias.obtener_incidencia(incidencia_id)
    if incidencia is None:
        raise ReglaNegocioError(f"No existe la incidencia #{incidencia_id}.")
    if incidencia.estado is EstadoIncidencia.cerrada:
        raise ReglaNegocioError(f"La incidencia #{incidencia_id} ya está cerrada.")
    cerrada = repositorio_incidencias.cerrar_incidencia(incidencia_id)
    regla_central.liberar_por_cierre(cerrada)
    return cerrada
