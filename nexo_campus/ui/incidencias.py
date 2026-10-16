"""Incidencias: reporte con triaje por IA en dos pasos (propuesta y revisión) y tablero por prioridad."""

import streamlit as st

from nexo_campus.ai.triaje import AREA_POR_CATEGORIA, AREAS, CATEGORIAS
from nexo_campus.errors import IAError, NexoCampusError
from nexo_campus.models import Espacio, EstadoIncidencia, Incidencia, OrigenClasificacion, Prioridad, Recurso
from nexo_campus.repositories import catalogo
from nexo_campus.rules.central import PRIORIDADES_QUE_BLOQUEAN, bloquea
from nexo_campus.ui import componentes as ui
from nexo_campus.ui.estilos import COLORES

TITULO = "Incidencias"
DESCRIPCION = "Reporte, clasificación con IA y seguimiento de incidencias y solicitudes."

MODULO_INCIDENCIAS = "nexo_campus.services.incidencias"
CLAVE_REVISION = "nc_incidencia_en_revision"  # reporte esperando que la persona confirme la clasificación

# Orden del tablero: lo más urgente primero, lo que no tiene prioridad al final
ORDEN_PRIORIDAD = {Prioridad.critica: 0, Prioridad.alta: 1, Prioridad.media: 2, Prioridad.baja: 3, None: 4}


# --- Paso 1: reporte ------------------------------------------------------------------------------


def _formulario(espacios: list[Espacio], recursos: list[Recurso], habilitado: bool) -> None:
    opciones_espacio = {f"{e.id} · {e.nombre}": e.id for e in espacios}
    opciones_recurso = {f"{r.id} · {r.nombre}": r.id for r in recursos}

    with st.form("form_incidencia"):
        descripcion = st.text_area(
            "Descripción",
            placeholder="Describe el problema. Ej.: el proyector del aula 101 no enciende y hay clase a las 10.",
            height=120,
            disabled=not habilitado,
        )
        col1, col2, col3 = st.columns(3)
        reportante = col1.text_input("Reportado por", disabled=not habilitado)
        espacio = col2.selectbox("Espacio afectado", list(opciones_espacio), index=None, placeholder="Ninguno", disabled=not habilitado)
        recurso = col3.selectbox("Equipo afectado", list(opciones_recurso), index=None, placeholder="Ninguno", disabled=not habilitado)
        col_ia, col_manual, _ = st.columns([1.2, 1.4, 2])
        analizar = col_ia.form_submit_button("Analizar con IA", type="primary", disabled=not habilitado)
        manual = col_manual.form_submit_button("Clasificar manualmente", disabled=not habilitado)

    if not (analizar or manual):
        return

    reporte = {
        "descripcion": descripcion,
        "reportante": reportante,
        "espacio_id": opciones_espacio.get(espacio),
        "recurso_id": opciones_recurso.get(recurso),
        "propuesta": None,
        "error_ia": None,
    }
    if not descripcion.strip():
        st.error("Describe la incidencia antes de continuar.", icon="⚠️")
        return

    if analizar:
        from nexo_campus.services import incidencias as servicio

        try:
            with st.spinner("Analizando con IA..."):
                reporte["propuesta"] = servicio.analizar_incidencia(descripcion, reporte["espacio_id"], reporte["recurso_id"])
        except IAError as exc:
            reporte["error_ia"] = str(exc)  # se sigue con clasificación manual, nunca con una respuesta inventada
        except NexoCampusError as exc:
            st.error(str(exc), icon="⚠️")
            return

    st.session_state[CLAVE_REVISION] = reporte
    st.rerun()


# --- Paso 2: revisión y registro ------------------------------------------------------------------


def _revision(reporte: dict) -> None:
    from nexo_campus.services import incidencias as servicio

    propuesta = reporte["propuesta"]
    afectado = " · ".join(filter(None, [reporte["espacio_id"], reporte["recurso_id"]])) or "Sin espacio ni equipo asociado"

    if propuesta is not None:
        ui.grilla(
            [
                ui.tarjeta_item(
                    "Propuesta de la IA",
                    [ui.badge(propuesta.prioridad.value)],
                    [f"Categoría: {ui.texto(propuesta.categoria)} · Área: {ui.texto(propuesta.area_responsable)}", f"Afecta: {afectado}"],
                    propuesta.justificacion,
                )
            ],
            columnas=1,
        )
        st.caption("Revisa la propuesta. Si la aceptas sin cambios queda como clasificada por IA; si la corriges, como manual.")
    elif reporte["error_ia"]:
        st.warning(f"La IA no pudo clasificar la incidencia: {reporte['error_ia']} Clasifícala manualmente.", icon="🛰️")
    else:
        st.caption(f"Clasificación manual · Afecta: {afectado}")

    ui.grilla([ui.tarjeta_item("Reporte", [], [], reporte["descripcion"])], columnas=1)

    with st.form("form_revision"):
        col_categoria, col_prioridad, col_area = st.columns(3)
        categoria = col_categoria.selectbox(
            "Categoría", CATEGORIAS,
            index=CATEGORIAS.index(propuesta.categoria) if propuesta else None,
            placeholder="Selecciona una categoría", format_func=ui.texto,
        )
        prioridades = list(Prioridad)
        prioridad = col_prioridad.selectbox(
            "Prioridad", prioridades,
            index=prioridades.index(propuesta.prioridad) if propuesta else None,
            placeholder="Selecciona una prioridad", format_func=lambda p: ui.etiqueta(p.value),
        )
        area = col_area.selectbox(
            "Área responsable", AREAS,
            index=AREAS.index(propuesta.area_responsable) if propuesta else None,
            placeholder="Según la categoría", format_func=ui.texto,
        )
        st.caption(
            "Enrutamiento por categoría: "
            + " · ".join(f"{ui.texto(c)} → {ui.texto(a)}" for c, a in AREA_POR_CATEGORIA.items())
            + ". Si dejas el área vacía se usa la de la categoría."
        )
        col_registrar, col_descartar, _ = st.columns([1.2, 1, 2.6])
        registrar = col_registrar.form_submit_button("Registrar incidencia", type="primary")
        descartar = col_descartar.form_submit_button("Descartar")

    if descartar:
        st.session_state.pop(CLAVE_REVISION, None)
        st.rerun()
    if not registrar:
        return
    if categoria is None or prioridad is None:
        st.error("Elige la categoría y la prioridad antes de registrar.", icon="⚠️")
        return
    area = area or AREA_POR_CATEGORIA.get(categoria)
    if area is None:
        st.error("La categoría 'Otro' no tiene un área fija: elige el área responsable.", icon="⚠️")
        return

    origen = servicio.origen_segun_propuesta(propuesta, categoria, prioridad, area)

    def _registrar() -> Incidencia:
        incidencia = servicio.registrar_incidencia(
            reporte["descripcion"], reporte["reportante"], reporte["espacio_id"], reporte["recurso_id"],
            categoria, prioridad, area,
            # La justificación es de la IA: solo se guarda si la propuesta se aceptó tal cual.
            propuesta.justificacion if origen is OrigenClasificacion.ia else None,
            origen,
        )
        st.session_state.pop(CLAVE_REVISION, None)
        return incidencia

    def _mensaje(incidencia: Incidencia) -> str:
        from nexo_campus.services import regla_central

        texto = (
            f"Incidencia #{incidencia.id} registrada · {ui.etiqueta(incidencia.origen_clasificacion.value)} · "
            f"enviada a {ui.texto(incidencia.area_responsable)}."
        )
        bloqueo = regla_central.describir_bloqueo(incidencia)
        return f"{texto} ⛔ {bloqueo}." if bloqueo else texto

    ui.ejecutar(_registrar, _mensaje, recargar=True)


def _como_funciona() -> None:
    ui.lista_clave_valor(
        "Cómo se clasifica",
        [
            ("1. Reporte", "Texto libre"),
            ("2. Propuesta de la IA", "Categoría, prioridad y área"),
            ("3. Revisión", "Se acepta o se corrige"),
            ("4. Registro", "Queda marcado IA o manual"),
            ("Si la IA falla", "Clasificación manual"),
            (
                "Prioridad " + " o ".join(ui.etiqueta(p.value) for p in sorted(PRIORIDADES_QUE_BLOQUEAN, key=lambda p: p.value)),
                "Inhabilita el espacio o equipo hasta cerrarse",
            ),
        ],
    )


# --- Tablero --------------------------------------------------------------------------------------


def _tarjeta(incidencia: Incidencia) -> str:
    badges = [ui.badge(incidencia.prioridad.value if incidencia.prioridad else None), ui.badge(incidencia.estado.value)]
    afectado = " · ".join(filter(None, [incidencia.espacio_id, incidencia.recurso_id]))
    meta = [
        f"#{incidencia.codigo_origen or incidencia.id}" + (f" · {afectado}" if afectado else ""),
        incidencia.area_responsable and f"Área: {ui.texto(incidencia.area_responsable)}",
        incidencia.origen_clasificacion and ui.etiqueta(incidencia.origen_clasificacion.value),
        incidencia.fecha_reporte and f"Reportada: {incidencia.fecha_reporte:%d/%m/%Y %H:%M}",
    ]
    if afectado and incidencia.estado is not EstadoIncidencia.cerrada and bloquea(incidencia.prioridad):
        meta.insert(0, f"⛔ Mantiene inhabilitado: {afectado}")
    titulo = ui.texto(incidencia.categoria) if incidencia.categoria else "Sin categoría"
    return ui.tarjeta_item(titulo, badges, meta, incidencia.descripcion)


def _cerrar(abiertas: list[Incidencia]) -> None:
    from nexo_campus.services import incidencias as servicio

    opciones = {i.id: i for i in sorted(abiertas, key=lambda i: ORDEN_PRIORIDAD[i.prioridad])}
    col_selector, col_boton = st.columns([4, 1], vertical_alignment="bottom")
    elegida = col_selector.selectbox(
        "Cerrar una incidencia", list(opciones), index=None,
        placeholder="Selecciona una incidencia abierta" if opciones else "No hay incidencias abiertas",
        format_func=lambda i: f"#{opciones[i].codigo_origen or i} · {ui.etiqueta(opciones[i].prioridad.value) if opciones[i].prioridad else '—'} · {opciones[i].descripcion[:70]}",
        disabled=not opciones, key="cerrar_incidencia",
    )
    def _mensaje(incidencia: Incidencia) -> str:
        from nexo_campus.services import regla_central

        liberacion = regla_central.describir_liberacion(incidencia)
        return f"Incidencia #{incidencia.id} cerrada. ✅ {liberacion}." if liberacion else f"Incidencia #{incidencia.id} cerrada."

    if col_boton.button("Cerrar incidencia", use_container_width=True, disabled=elegida is None):
        ui.ejecutar(lambda: servicio.cerrar_incidencia(elegida), _mensaje, recargar=True)


def _tablero(incidencias: list[Incidencia], servicio_listo: bool) -> None:
    if not incidencias:
        ui.estado_vacio("No hay incidencias registradas", "Las incidencias reportadas aparecerán aquí ordenadas por prioridad.")
        return

    if servicio_listo:
        _cerrar([i for i in incidencias if i.estado is not EstadoIncidencia.cerrada])

    col_estado, col_prioridad, col_total = st.columns(3, vertical_alignment="bottom")
    estado = col_estado.selectbox(
        "Estado", ["pendientes", "todas", *[e.value for e in EstadoIncidencia]],
        format_func=lambda v: {"pendientes": "Abiertas y en proceso", "todas": "Todas"}.get(v, ui.etiqueta(v)),
        key="estado_incidencia",
    )
    prioridad = col_prioridad.selectbox(
        "Prioridad", ["todas", *[p.value for p in Prioridad]],
        format_func=lambda v: "Todas" if v == "todas" else ui.etiqueta(v),
        key="prioridad_incidencia",
    )
    filtradas = sorted(
        (
            i for i in incidencias
            if (estado == "todas" or (estado == "pendientes" and i.estado is not EstadoIncidencia.cerrada) or i.estado.value == estado)
            and (prioridad == "todas" or (i.prioridad and i.prioridad.value == prioridad))
        ),
        key=lambda i: ORDEN_PRIORIDAD[i.prioridad],
    )
    col_total.caption(f"{len(filtradas)} de {len(incidencias)} incidencias")

    if not filtradas:
        st.caption("Ninguna incidencia coincide con los filtros.")
        return
    # Altura fija: la lista se desplaza dentro de su recuadro y la página no se alarga.
    with st.container(height=480, border=False):
        ui.grilla([_tarjeta(i) for i in filtradas], columnas=2)


def mostrar() -> None:
    espacios = catalogo.listar_espacios()
    recursos = catalogo.listar_recursos()
    incidencias = catalogo.listar_incidencias()
    servicio_listo = ui.modulo_disponible(MODULO_INCIDENCIAS)
    abiertas = [i for i in incidencias if i.estado is not EstadoIncidencia.cerrada]

    ui.fila_metricas(
        [
            ("Abiertas", len(abiertas), "pendientes de atención", COLORES["alerta"]),
            ("Críticas", sum(i.prioridad is Prioridad.critica for i in abiertas), "requieren acción inmediata", COLORES["peligro"]),
            ("Clasificadas por IA", sum(i.origen_clasificacion is OrigenClasificacion.ia for i in incidencias), "aceptadas sin cambios", COLORES["primario"]),
            ("Cerradas", len(incidencias) - len(abiertas), "resueltas", COLORES["exito"]),
        ]
    )

    # "Reportar" va primero: tras registrar, la página se recarga y vuelve a la primera pestaña.
    pestana_reportar, pestana_tablero = st.tabs(["Reportar incidencia", f"Tablero ({len(abiertas)} abiertas)"])
    with pestana_reportar:
        if not servicio_listo:
            st.info("El reporte con IA se activará cuando exista el servicio de incidencias (nexo_campus/services/incidencias.py).", icon="🛠️")
        col_formulario, col_info = st.columns([2.2, 1])
        with col_formulario:
            reporte = st.session_state.get(CLAVE_REVISION)
            if reporte and servicio_listo:
                _revision(reporte)
            else:
                _formulario(espacios, recursos, habilitado=servicio_listo)
        with col_info:
            _como_funciona()
    with pestana_tablero:
        _tablero(incidencias, servicio_listo)
