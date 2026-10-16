"""Carga los datos oficiales de data/raw/ a SQLite y registra cada inconsistencia encontrada.

Ningún registro inválido se descarta en silencio: queda en la tabla RegistroInconsistente con su motivo.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, select

from nexo_campus import config, db
from nexo_campus.carga import normalizacion as n
from nexo_campus.carga.esquema import (
    ALIAS_ESTADO_ESPACIO,
    ALIAS_ESTADO_INCIDENCIA,
    ALIAS_ESTADO_PRESTAMO,
    ALIAS_ESTADO_RECURSO,
    ALIAS_ESTADO_RESERVA,
    ALIAS_PRIORIDAD,
    ARCHIVOS,
    COLUMNAS,
    OBLIGATORIAS,
)
from nexo_campus.carga.lectura import buscar_archivo, leer_tabla, mapear_columnas
from nexo_campus.carga.normalizacion import DatoInvalido
from nexo_campus.errors import DatosInconsistentesError, NexoCampusError, ReglaNegocioError
from nexo_campus.models import (
    Espacio,
    EstadoEspacio,
    EstadoIncidencia,
    EstadoPrestamo,
    EstadoRecurso,
    EstadoReserva,
    HistorialEstadoRecurso,
    Incidencia,
    OrigenCambioEstado,
    OrigenClasificacion,
    Prestamo,
    Prioridad,
    Recurso,
    RegistroInconsistente,
    Reserva,
    TipoInconsistencia,
)
from nexo_campus.rules import reservas as reglas_reservas

# Orden de carga: primero lo que otros registros referencian
ENTIDADES = ("espacios", "recursos", "reservas", "prestamos", "incidencias")
MODELOS = (Espacio, Recurso, Reserva, Prestamo, Incidencia)


@dataclass
class ResumenEntidad:
    entidad: str
    archivo: str | None = None
    leidos: int = 0
    cargados: int = 0
    rechazados: int = 0
    advertencias: int = 0


@dataclass
class ReporteCarga:
    resumen: list[ResumenEntidad]
    inconsistencias: list[RegistroInconsistente]

    @property
    def total_cargados(self) -> int:
        return sum(r.cargados for r in self.resumen)

    @property
    def total_rechazados(self) -> int:
        return sum(r.rechazados for r in self.resumen)


@dataclass
class _Contexto:
    """Lo ya cargado, para validar referencias y conflictos entre registros."""

    espacios: dict[str, Espacio] = field(default_factory=dict)
    recursos: dict[str, Recurso] = field(default_factory=dict)
    filas_recursos: dict[str, int] = field(default_factory=dict)
    reservas_activas: dict[str, list[Reserva]] = field(default_factory=lambda: defaultdict(list))
    filas_reservas: dict[int, int] = field(default_factory=dict)  # id(reserva) -> fila del archivo
    prestamos_activos: dict[str, int] = field(default_factory=dict)
    inconsistencias: list[RegistroInconsistente] = field(default_factory=list)
    historial: list[HistorialEstadoRecurso] = field(default_factory=list)

    def registrar(
        self,
        entidad: str,
        archivo: str | None,
        fila: int | None,
        identificador: str | None,
        motivo: str,
        tipo: TipoInconsistencia,
    ) -> None:
        self.inconsistencias.append(
            RegistroInconsistente(
                entidad=entidad, archivo=archivo, fila=fila, identificador=identificador, motivo=motivo, tipo=tipo
            )
        )


# --- Conversión y validación de cada tipo de registro --------------------------------------------


def _a_espacio(f: dict[str, str], ctx: _Contexto, avisos: list[str], fila: int) -> Espacio:
    espacio = Espacio(
        id=n.codigo(f.get("id"), "id"),
        nombre=n.texto(f.get("nombre"), "nombre"),
        tipo=n.clave(f.get("tipo"), "tipo", por_defecto="sin_tipo", avisos=avisos),
        aforo=n.entero(f.get("aforo"), "aforo", minimo=1),
        ubicacion=n.texto(f.get("ubicacion"), "ubicacion", obligatorio=False),
        estado=n.opcion(
            f.get("estado"), "estado", EstadoEspacio, ALIAS_ESTADO_ESPACIO,
            por_defecto=EstadoEspacio.disponible, avisos=avisos,
        ),
    )
    ctx.espacios[espacio.id] = espacio
    return espacio


def _a_recurso(f: dict[str, str], ctx: _Contexto, avisos: list[str], fila: int) -> Recurso:
    recurso = Recurso(
        id=n.codigo(f.get("id"), "id"),
        nombre=n.texto(f.get("nombre"), "nombre"),
        tipo=n.clave(f.get("tipo"), "tipo", por_defecto="sin_tipo", avisos=avisos),
        estado=n.opcion(
            f.get("estado"), "estado", EstadoRecurso, ALIAS_ESTADO_RECURSO,
            por_defecto=EstadoRecurso.disponible, avisos=avisos,
        ),
        ubicacion=n.texto(f.get("ubicacion"), "ubicacion", obligatorio=False),
    )
    ctx.recursos[recurso.id] = recurso
    ctx.filas_recursos[recurso.id] = fila
    return recurso


def _a_reserva(f: dict[str, str], ctx: _Contexto, avisos: list[str], fila: int) -> Reserva:
    espacio_id = n.codigo(f.get("espacio_id"), "espacio_id")
    espacio = ctx.espacios.get(espacio_id)
    if espacio is None:
        raise DatoInvalido(f"El espacio '{espacio_id}' no existe en espacios (ID huérfano)")

    fecha = n.fecha_hora(f.get("fecha"), "fecha", obligatorio=False)
    inicio = n.fecha_hora(f.get("inicio"), "inicio", fecha_base=fecha)
    fin = n.fecha_hora(f.get("fin"), "fin", fecha_base=fecha)
    if fin <= inicio:
        raise DatoInvalido(f"La hora de fin ({fin:%Y-%m-%d %H:%M}) no es posterior a la de inicio ({inicio:%Y-%m-%d %H:%M})")

    asistentes = n.entero(f.get("asistentes"), "asistentes", minimo=1)
    estado = n.opcion(
        f.get("estado"), "estado", EstadoReserva, ALIAS_ESTADO_RESERVA,
        por_defecto=EstadoReserva.activa, avisos=avisos,
    )
    solicitante = n.texto(f.get("solicitante"), "solicitante")

    reserva = Reserva(
        codigo_origen=n.codigo(f.get("id"), "id", obligatorio=False),
        espacio_id=espacio_id,
        solicitante=solicitante,
        inicio=inicio,
        fin=fin,
        asistentes=asistentes,
        motivo=n.texto(f.get("motivo"), "motivo", obligatorio=False),
        estado=estado,
    )

    # Una reserva cancelada no ocupa el espacio, así que no entra en conflicto con nada.
    if estado is EstadoReserva.activa:
        _validar_reserva_activa(reserva, espacio, ctx)
        ctx.reservas_activas[espacio_id].append(reserva)
        ctx.filas_reservas[id(reserva)] = fila

    return reserva


def _validar_reserva_activa(reserva: Reserva, espacio: Espacio, ctx: _Contexto) -> None:
    """Aplica las mismas reglas de aforo y solapamiento que la aplicación (rules/reservas.py)."""
    conflictos = [
        otra for otra in ctx.reservas_activas[espacio.id]
        if reglas_reservas.se_solapan(otra.inicio, otra.fin, reserva.inicio, reserva.fin)
    ]
    try:
        reglas_reservas.validar_aforo(reserva.asistentes, espacio.aforo)
    except ReglaNegocioError as exc:
        raise DatoInvalido(str(exc)) from exc
    try:
        reglas_reservas.validar_sin_solapamiento(conflictos)
    except ReglaNegocioError as exc:
        filas = ", ".join(str(ctx.filas_reservas[id(otra)]) for otra in conflictos)
        raise DatoInvalido(f"{exc} Se solapa con la fila {filas}.") from exc


def _a_prestamo(f: dict[str, str], ctx: _Contexto, avisos: list[str], fila: int) -> Prestamo:
    recurso_id = n.codigo(f.get("recurso_id"), "recurso_id")
    if recurso_id not in ctx.recursos:
        raise DatoInvalido(f"El recurso '{recurso_id}' no existe en recursos (ID huérfano)")

    solicitante = n.texto(f.get("solicitante"), "solicitante")
    fecha_prestamo = n.fecha_hora(f.get("fecha_prestamo"), "fecha_prestamo")
    prevista = n.fecha_hora(f.get("fecha_devolucion_prevista"), "fecha_devolucion_prevista", obligatorio=False)
    devolucion = n.fecha_hora(f.get("fecha_devolucion"), "fecha_devolucion", obligatorio=False)
    if prevista and prevista < fecha_prestamo:
        raise DatoInvalido("La devolución prevista es anterior a la fecha del préstamo")
    if devolucion and devolucion < fecha_prestamo:
        raise DatoInvalido("La fecha de devolución es anterior a la fecha del préstamo")

    estado = n.opcion(f.get("estado"), "estado", EstadoPrestamo, ALIAS_ESTADO_PRESTAMO, obligatorio=False)
    if estado is None:
        estado = EstadoPrestamo.devuelto if devolucion else EstadoPrestamo.activo
        avisos.append(f"'estado' vacío; se dedujo '{estado.value}' a partir de la fecha de devolución")
    if estado is EstadoPrestamo.activo and devolucion:
        raise DatoInvalido("El préstamo figura como activo pero tiene fecha de devolución")
    if estado is EstadoPrestamo.devuelto and not devolucion:
        avisos.append("El préstamo figura como devuelto pero no tiene fecha de devolución")

    if estado is EstadoPrestamo.activo:
        if recurso_id in ctx.prestamos_activos:
            raise DatoInvalido(
                f"El recurso {recurso_id} ya tiene un préstamo activo (fila {ctx.prestamos_activos[recurso_id]})"
            )
        ctx.prestamos_activos[recurso_id] = fila

    return Prestamo(
        codigo_origen=n.codigo(f.get("id"), "id", obligatorio=False),
        recurso_id=recurso_id,
        solicitante=solicitante,
        fecha_prestamo=fecha_prestamo,
        fecha_devolucion_prevista=prevista,
        fecha_devolucion=devolucion,
        estado=estado,
    )


def _a_incidencia(f: dict[str, str], ctx: _Contexto, avisos: list[str], fila: int) -> Incidencia:
    espacio_id = n.codigo(f.get("espacio_id"), "espacio_id", obligatorio=False)
    if espacio_id and espacio_id not in ctx.espacios:
        raise DatoInvalido(f"El espacio '{espacio_id}' no existe en espacios (ID huérfano)")
    recurso_id = n.codigo(f.get("recurso_id"), "recurso_id", obligatorio=False)
    if recurso_id and recurso_id not in ctx.recursos:
        raise DatoInvalido(f"El recurso '{recurso_id}' no existe en recursos (ID huérfano)")

    fecha_reporte = n.fecha_hora(f.get("fecha_reporte"), "fecha_reporte", obligatorio=False)
    fecha_cierre = n.fecha_hora(f.get("fecha_cierre"), "fecha_cierre", obligatorio=False)
    if fecha_reporte and fecha_cierre and fecha_cierre < fecha_reporte:
        raise DatoInvalido("La fecha de cierre es anterior a la fecha de reporte")

    categoria = n.clave(f.get("categoria"), "categoria")
    prioridad = n.opcion(f.get("prioridad"), "prioridad", Prioridad, ALIAS_PRIORIDAD, obligatorio=False)
    return Incidencia(
        codigo_origen=n.codigo(f.get("id"), "id", obligatorio=False),
        descripcion=n.texto(f.get("descripcion"), "descripcion"),
        reportante=n.texto(f.get("reportante"), "reportante", obligatorio=False),
        espacio_id=espacio_id,
        recurso_id=recurso_id,
        fecha_reporte=fecha_reporte,
        categoria=categoria,
        prioridad=prioridad,
        area_responsable=n.texto(f.get("area_responsable"), "area_responsable", obligatorio=False),
        origen_clasificacion=OrigenClasificacion.datos_origen if (categoria or prioridad) else None,
        estado=n.opcion(
            f.get("estado"), "estado", EstadoIncidencia, ALIAS_ESTADO_INCIDENCIA,
            por_defecto=EstadoIncidencia.abierta, avisos=avisos,
        ),
        fecha_cierre=fecha_cierre,
    )


Convertidor = Callable[[dict[str, str], _Contexto, list[str], int], SQLModel]
CONVERTIDORES: dict[str, Convertidor] = {
    "espacios": _a_espacio,
    "recursos": _a_recurso,
    "reservas": _a_reserva,
    "prestamos": _a_prestamo,
    "incidencias": _a_incidencia,
}


# --- Proceso de carga ----------------------------------------------------------------------------


def _cargar_entidad(entidad: str, directorio: Path, ctx: _Contexto) -> tuple[ResumenEntidad, list[SQLModel]]:
    resumen = ResumenEntidad(entidad=entidad)
    ruta = buscar_archivo(directorio, ARCHIVOS[entidad])
    if ruta is None:
        ctx.registrar(
            entidad, None, None, None,
            f"No se encontró el archivo '{ARCHIVOS[entidad]}' (.csv, .xlsx, .xls o .json)",
            TipoInconsistencia.advertencia,
        )
        return resumen, []
    resumen.archivo = ruta.name

    try:
        tabla = leer_tabla(ruta)
    except DatosInconsistentesError as exc:
        ctx.registrar(entidad, ruta.name, None, None, str(exc), TipoInconsistencia.rechazado)
        return resumen, []

    filas, faltantes = mapear_columnas(tabla, COLUMNAS[entidad])
    sin_columna = [campo for campo in OBLIGATORIAS[entidad] if campo in faltantes]
    if sin_columna:
        ctx.registrar(
            entidad, ruta.name, None, None,
            f"Faltan columnas obligatorias: {', '.join(sin_columna)}. Columnas del archivo: {', '.join(tabla.columnas)}",
            TipoInconsistencia.rechazado,
        )
        resumen.leidos = resumen.rechazados = len(filas)
        return resumen, []

    convertir = CONVERTIDORES[entidad]
    objetos: list[SQLModel] = []
    filas_vistas: dict[tuple[str, ...], int] = {}
    ids_vistos: dict[str, int] = {}

    for posicion, fila in enumerate(filas):
        numero = tabla.primera_fila + posicion
        resumen.leidos += 1
        identificador = n.codigo(fila.get("id"), "id", obligatorio=False)
        firma = tuple(" ".join(valor.split()).lower() for valor in fila.values())
        avisos: list[str] = []
        try:
            if firma in filas_vistas:
                raise DatoInvalido(f"Fila duplicada (idéntica a la fila {filas_vistas[firma]})")
            filas_vistas[firma] = numero
            if identificador and identificador in ids_vistos:
                raise DatoInvalido(f"ID duplicado '{identificador}' (ya aparece en la fila {ids_vistos[identificador]})")
            objeto = convertir(fila, ctx, avisos, numero)
        except DatoInvalido as exc:
            ctx.registrar(entidad, ruta.name, numero, identificador, str(exc), TipoInconsistencia.rechazado)
            resumen.rechazados += 1
            continue

        if identificador:
            ids_vistos[identificador] = numero
        for aviso in avisos:
            ctx.registrar(entidad, ruta.name, numero, identificador, aviso, TipoInconsistencia.advertencia)
        resumen.advertencias += len(avisos)
        resumen.cargados += 1
        objetos.append(objeto)

    return resumen, objetos


def _conciliar_estados_recursos(ctx: _Contexto, resumen: ResumenEntidad) -> None:
    """El estado de cada equipo debe coincidir con sus préstamos activos. Cada corrección queda en el historial."""
    for recurso_id, recurso in ctx.recursos.items():
        prestado = recurso_id in ctx.prestamos_activos
        motivo = None
        nuevo_estado = None
        if prestado and recurso.estado is EstadoRecurso.disponible:
            nuevo_estado = EstadoRecurso.prestado
            motivo = "Figuraba 'disponible' pero tiene un préstamo activo; se cambió a 'prestado'"
        elif prestado and recurso.estado is not EstadoRecurso.prestado:
            motivo = f"Tiene un préstamo activo pero su estado es '{recurso.estado.value}'"
        elif not prestado and recurso.estado is EstadoRecurso.prestado:
            nuevo_estado = EstadoRecurso.disponible
            motivo = "Figuraba 'prestado' sin ningún préstamo activo; se cambió a 'disponible'"
        if nuevo_estado is not None:
            ctx.historial.append(
                HistorialEstadoRecurso(
                    recurso_id=recurso_id, estado_anterior=recurso.estado, estado_nuevo=nuevo_estado,
                    motivo=motivo, origen=OrigenCambioEstado.carga,
                )
            )
            recurso.estado = nuevo_estado
        if motivo:
            ctx.registrar(
                "recursos", resumen.archivo, ctx.filas_recursos.get(recurso_id), recurso_id,
                motivo, TipoInconsistencia.advertencia,
            )
            resumen.advertencias += 1


def _hay_datos(motor_db: Engine) -> bool:
    with db.obtener_sesion(motor_db) as sesion:
        return any(sesion.exec(select(modelo).limit(1)).first() for modelo in MODELOS)


def cargar_datos(
    motor_db: Engine = db.motor, directorio: Path | None = None, reiniciar: bool = False
) -> ReporteCarga:
    """Carga todos los archivos de datos oficiales en una base de datos vacía.

    Si la base ya tiene información, solo la reemplaza con reiniciar=True.
    """
    directorio = Path(directorio or config.DATA_DIR)
    if not directorio.is_dir():
        raise DatosInconsistentesError(f"No existe la carpeta de datos: {directorio}")

    db.crear_tablas(motor_db)
    if _hay_datos(motor_db) and not reiniciar:
        raise NexoCampusError(
            "La base de datos ya tiene información. Para recargar desde cero usa la opción --reiniciar "
            "(se perderán los cambios hechos desde la aplicación)."
        )
    db.reiniciar_tablas(motor_db)

    ctx = _Contexto()
    resumen: list[ResumenEntidad] = []
    with db.obtener_sesion(motor_db) as sesion:
        for entidad in ENTIDADES:
            resumen_entidad, objetos = _cargar_entidad(entidad, directorio, ctx)
            resumen.append(resumen_entidad)
            sesion.add_all(objetos)
            sesion.flush()  # inserta en orden para que las claves foráneas ya existan
        _conciliar_estados_recursos(ctx, next(r for r in resumen if r.entidad == "recursos"))
        sesion.add_all(ctx.historial)
        sesion.add_all(ctx.inconsistencias)
        sesion.commit()

    return ReporteCarga(resumen=resumen, inconsistencias=ctx.inconsistencias)
