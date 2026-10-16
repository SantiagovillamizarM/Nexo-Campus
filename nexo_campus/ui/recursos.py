"""Recursos: inventario de equipos, préstamos e historial de estados."""

from datetime import date, datetime, time, timedelta

import streamlit as st

from nexo_campus.models import EstadoPrestamo, EstadoRecurso, Prestamo, Recurso
from nexo_campus.repositories import catalogo
from nexo_campus.ui import componentes as ui
from nexo_campus.ui.estilos import COLORES

TITULO = "Recursos"
DESCRIPCION = "Préstamo y control de los equipos tecnológicos, con trazabilidad de su estado."

MODULO_PRESTAMOS = "nexo_campus.services.prestamos"


def _resumen(recursos: list[Recurso]) -> None:
    def contar(*estados: EstadoRecurso) -> int:
        return sum(r.estado in estados for r in recursos)

    ui.fila_metricas(
        [
            ("Disponibles", contar(EstadoRecurso.disponible), "listos para prestar", COLORES["exito"]),
            ("Prestados", contar(EstadoRecurso.prestado), "en uso", COLORES["info"]),
            ("Mantenimiento", contar(EstadoRecurso.mantenimiento), "en revisión", COLORES["alerta"]),
            ("Fuera de servicio", contar(EstadoRecurso.danado, EstadoRecurso.inhabilitado), "dañados o inhabilitados", COLORES["peligro"]),
        ]
    )


def _inventario(recursos: list[Recurso]) -> None:
    if not recursos:
        ui.estado_vacio("No hay recursos cargados", "Se mostrarán aquí después de cargar los datos oficiales.")
        return

    col_busqueda, col_tipo, col_estado = st.columns([2, 1, 1])
    busqueda = col_busqueda.text_input("Buscar", placeholder="Código o nombre", key="buscar_recurso")
    tipo = col_tipo.selectbox(
        "Tipo", ["Todos", *sorted({r.tipo for r in recursos})],
        format_func=ui.texto, key="tipo_recurso",
    )
    estado = col_estado.selectbox(
        "Estado", ["Todos", *sorted({r.estado.value for r in recursos})],
        format_func=lambda v: v if v == "Todos" else ui.etiqueta(v), key="estado_recurso",
    )

    texto = busqueda.strip().lower()
    filtrados = [
        r for r in recursos
        if (not texto or texto in r.id.lower() or texto in r.nombre.lower())
        and (tipo == "Todos" or r.tipo == tipo)
        and (estado == "Todos" or r.estado.value == estado)
    ]
    st.caption(f"{len(filtrados)} de {len(recursos)} recursos")
    if filtrados:
        ui.tabla(
            [
                {
                    "Código": r.id,
                    "Nombre": r.nombre,
                    "Tipo": ui.texto(r.tipo),
                    "Ubicación": r.ubicacion or "—",
                    "Estado": ui.etiqueta(r.estado.value),
                }
                for r in filtrados
            ],
            altura=380,
        )


def _acciones_prestamo(recursos: list[Recurso], activos: list[Prestamo]) -> None:
    """Formularios de préstamo y devolución. Llaman a services/prestamos.py (reglas 4 y 5)."""
    from nexo_campus.services import prestamos as servicio

    disponibles = {f"{r.id} · {r.nombre}": r.id for r in recursos if r.estado is EstadoRecurso.disponible}
    col_prestar, col_devolver = st.columns(2)

    with col_prestar, st.form("form_prestamo", clear_on_submit=True):
        ui.seccion("Prestar un equipo")
        equipo = st.selectbox("Equipo disponible", list(disponibles), index=None, placeholder="Selecciona un equipo")
        solicitante = st.text_input("Solicitante")
        devolucion = st.date_input("Devolución prevista", value=date.today() + timedelta(days=1), format="DD/MM/YYYY")
        if st.form_submit_button("Registrar préstamo", type="primary"):
            if equipo is None:
                st.error("Selecciona un equipo.", icon="⚠️")
            else:
                ui.ejecutar(
                    lambda: servicio.prestar_recurso(disponibles[equipo], solicitante, datetime.combine(devolucion, time(18, 0))),
                    "Préstamo registrado.",
                    recargar=True,
                )

    prestados = {f"#{p.id} · {p.recurso_id} · {p.solicitante}": p.id for p in activos}
    with col_devolver, st.form("form_devolucion", clear_on_submit=True):
        ui.seccion("Registrar una devolución")
        prestamo = st.selectbox("Préstamo activo", list(prestados), index=None, placeholder="Selecciona un préstamo")
        estado_final = st.radio(
            "El equipo vuelve", [EstadoRecurso.disponible, EstadoRecurso.danado],
            format_func=lambda e: ui.etiqueta(e.value), horizontal=True,
        )
        observacion = st.text_input("Observación (opcional)")
        if st.form_submit_button("Registrar devolución"):
            if prestamo is None:
                st.error("Selecciona un préstamo.", icon="⚠️")
            else:
                ui.ejecutar(
                    lambda: servicio.devolver_recurso(prestados[prestamo], estado_final, observacion),
                    "Devolución registrada.",
                    recargar=True,
                )


def _prestamos(recursos: list[Recurso]) -> None:
    from nexo_campus.repositories import prestamos as repositorio

    todos = repositorio.listar_prestamos()
    activos = [p for p in todos if p.estado is EstadoPrestamo.activo]

    if ui.modulo_disponible(MODULO_PRESTAMOS):
        _acciones_prestamo(recursos, activos)
    else:
        st.info("Prestar y devolver se activará cuando exista el servicio de préstamos (nexo_campus/services/prestamos.py).", icon="🛠️")

    if not todos:
        ui.estado_vacio("No hay préstamos registrados", "Los préstamos aparecerán aquí con su estado.")
        return
    filtro = st.radio(
        "Mostrar", ["activos", "devueltos", "todos"],
        format_func=lambda f: {"activos": f"Activos ({len(activos)})", "devueltos": f"Devueltos ({len(todos) - len(activos)})", "todos": "Todos"}[f],
        horizontal=True, label_visibility="collapsed", key="filtro_prestamos",
    )
    visibles = {"activos": activos, "devueltos": [p for p in todos if p.estado is EstadoPrestamo.devuelto], "todos": todos}[filtro]
    nombres = {r.id: r.nombre for r in recursos}
    ui.tabla(
        [
            {
                "#": p.id,
                "Equipo": f"{p.recurso_id} · {nombres.get(p.recurso_id, '')}",
                "Solicitante": p.solicitante,
                "Prestado": f"{p.fecha_prestamo:%d/%m/%Y %H:%M}",
                "Devolución prevista": f"{p.fecha_devolucion_prevista:%d/%m/%Y}" if p.fecha_devolucion_prevista else "—",
                "Devuelto": f"{p.fecha_devolucion:%d/%m/%Y %H:%M}" if p.fecha_devolucion else "—",
                "Estado": ui.etiqueta(p.estado.value),
            }
            for p in visibles
        ],
        altura=320,
    )


def _historial(recursos: list[Recurso]) -> None:
    from nexo_campus.repositories import prestamos as repositorio

    if not recursos:
        ui.estado_vacio("No hay recursos cargados", "El historial aparecerá después de cargar los datos oficiales.")
        return
    opciones = {f"{r.id} · {r.nombre} — {ui.etiqueta(r.estado.value)}": r.id for r in recursos}
    elegido = st.selectbox("Equipo", list(opciones), key="historial_recurso")
    cambios = repositorio.listar_historial(opciones[elegido])
    if not cambios:
        st.caption("Este equipo no ha cambiado de estado desde la carga de datos.")
        return
    ui.tabla(
        [
            {
                "Fecha": f"{c.fecha:%d/%m/%Y %H:%M}",
                "Estado anterior": ui.etiqueta(c.estado_anterior.value),
                "Estado nuevo": ui.etiqueta(c.estado_nuevo.value),
                "Origen": ui.etiqueta(c.origen.value),
                "Motivo": c.motivo or "—",
            }
            for c in cambios
        ],
        columnas_estado=("Estado anterior", "Estado nuevo"),
        altura=320,
    )


def _administrar(recursos: list[Recurso]) -> None:
    """Registrar equipos nuevos y editar los existentes. Los cambios de estado quedan en el historial."""
    from nexo_campus.rules.catalogo import ESTADOS_RECURSO_EDITABLES
    from nexo_campus.services import catalogo as servicio

    editables = list(ESTADOS_RECURSO_EDITABLES)
    col_nuevo, col_editar = st.columns(2)

    with col_nuevo:
        ui.seccion("Registrar un equipo")
        with st.form("form_nuevo_recurso", clear_on_submit=True):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código", placeholder="PC-001")
            nombre = c2.text_input("Nombre", placeholder="Portátil Lenovo 14")
            c3, c4 = st.columns(2)
            tipo = c3.text_input("Tipo", placeholder="portátil, proyector, tablet")
            ubicacion = c4.text_input("Ubicación (opcional)")
            estado = st.selectbox("Estado", editables, format_func=lambda e: ui.etiqueta(e.value))
            if st.form_submit_button("Registrar equipo", type="primary"):
                ui.ejecutar(
                    lambda: servicio.crear_recurso(codigo, nombre, tipo, ubicacion, estado),
                    lambda r: f"Equipo {r.id} registrado.",
                    recargar=True,
                )

    with col_editar:
        ui.seccion("Editar un equipo")
        if not recursos:
            st.caption("Todavía no hay equipos para editar.")
            return
        opciones = {r.id: r for r in recursos}
        elegido = st.selectbox("Equipo", list(opciones), format_func=lambda i: f"{i} · {opciones[i].nombre}", key="editar_recurso")
        recurso = opciones[elegido]
        estados = editables if recurso.estado in editables else [recurso.estado, *editables]
        with st.form(f"form_editar_recurso_{recurso.id}"):
            nombre = st.text_input("Nombre", value=recurso.nombre)
            c1, c2 = st.columns(2)
            tipo = c1.text_input("Tipo", value=ui.texto(recurso.tipo))
            ubicacion = c2.text_input("Ubicación", value=recurso.ubicacion or "")
            estado = st.selectbox("Estado", estados, index=estados.index(recurso.estado), format_func=lambda e: ui.etiqueta(e.value))
            motivo = st.text_input("Motivo del cambio de estado", placeholder="Ej. pantalla rota, enviado a revisión")
            if st.form_submit_button("Guardar cambios", type="primary"):
                ui.ejecutar(
                    lambda: servicio.actualizar_recurso(recurso.id, nombre, tipo, ubicacion, estado, motivo),
                    f"Equipo {recurso.id} actualizado.",
                    recargar=True,
                )


def mostrar() -> None:
    recursos = catalogo.listar_recursos()

    _resumen(recursos)
    pestana_inventario, pestana_prestamos, pestana_historial, pestana_admin = st.tabs(
        [f"Inventario ({len(recursos)})", "Préstamos", "Historial", "Administrar"]
    )
    with pestana_admin:
        _administrar(recursos)

    with pestana_inventario:
        _inventario(recursos)
    with pestana_prestamos:
        _prestamos(recursos)
    with pestana_historial:
        _historial(recursos)
