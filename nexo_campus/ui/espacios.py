"""Espacios: reservar, consultar reservas y catálogo de espacios."""

from datetime import date, datetime, time

import streamlit as st

from nexo_campus.errors import IAError, NexoCampusError
from nexo_campus.models import Espacio, EstadoEspacio, EstadoReserva
from nexo_campus.repositories import catalogo
from nexo_campus.rules import reservas as reglas
from nexo_campus.ui import componentes as ui

TITULO = "Espacios"
DESCRIPCION = "Reserva de aulas y cubículos sin cruces de horario ni exceso de aforo."

# El servicio de reservas necesita este repositorio (tarea de P1). Mientras no exista,
# el formulario se muestra desactivado en lugar de romper la aplicación.
MODULO_REPOSITORIO = "nexo_campus.repositories.reservas"


def _texto_pcs(pcs) -> str:
    """'34 PCs' o '32 de 34 PCs operativos' cuando hay equipos fuera de servicio."""
    if not pcs.total:
        return ""
    if not pcs.fuera_de_servicio:
        return f"{pcs.total} PCs"
    return f"{len(pcs.operativos)} de {pcs.total} PCs operativos"


def _formulario_reserva(espacios: list[Espacio], habilitado: bool) -> None:
    from nexo_campus.services import reservas as servicio

    # Se listan todos los espacios (también los no disponibles) para que la regla de estado explique el rechazo.
    pcs_por_sala = {e.id: servicio.pcs_de_la_sala(e.id) for e in espacios}
    opciones = {
        f"{e.id} · {e.nombre} (aforo {e.aforo}"
        + (f" · {_texto_pcs(pcs_por_sala[e.id])}" if pcs_por_sala[e.id].total else "")
        + f") — {ui.etiqueta(e.estado.value)}": e.id
        for e in espacios
    }

    with st.form("form_reserva"):
        col1, col2 = st.columns(2)
        espacio = col1.selectbox("Espacio", list(opciones), index=None, placeholder="Selecciona un espacio", disabled=not habilitado)
        solicitante = col2.text_input("Solicitante", placeholder="Nombre de quien reserva", disabled=not habilitado)

        col3, col4, col5, col6 = st.columns(4)
        fecha = col3.date_input("Fecha", value=date.today(), format="DD/MM/YYYY", disabled=not habilitado)
        hora_inicio = col4.time_input("Inicio", value=time(8, 0), step=1800, disabled=not habilitado)
        hora_fin = col5.time_input("Fin", value=time(10, 0), step=1800, disabled=not habilitado)
        asistentes = col6.number_input("Asistentes", min_value=1, value=1, step=1, disabled=not habilitado)

        motivo = st.text_input("Motivo (opcional)", placeholder="Ej. clase de refuerzo", disabled=not habilitado)
        enviado = st.form_submit_button("Confirmar reserva", type="primary", disabled=not habilitado)

    if not enviado:
        return
    if espacio is None:
        st.error("Selecciona un espacio para reservar.", icon="⚠️")
        return

    def _mensaje(reserva) -> str:
        # Reservar una sala de cómputo presta todos sus PCs operativos durante la franja.
        pcs = pcs_por_sala[reserva.espacio_id]
        if not pcs.total:
            return "Reserva confirmada."
        texto = f"Reserva confirmada · incluye el préstamo de {len(pcs.operativos)} PCs operativos de la sala"
        if pcs.fuera_de_servicio:
            texto += f" ({len(pcs.fuera_de_servicio)} fuera de servicio)"
        if reserva.asistentes > len(pcs.operativos):
            texto += f". ⚠️ Son {reserva.asistentes} asistentes y solo hay {len(pcs.operativos)} PCs operativos"
        return texto + "."

    inicio, fin = datetime.combine(fecha, hora_inicio), datetime.combine(fecha, hora_fin)
    with st.spinner("Validando aforo, horario y disponibilidad..."):
        reserva = ui.ejecutar(
            lambda: servicio.crear_reserva(opciones[espacio], solicitante, inicio, fin, int(asistentes), motivo),
            _mensaje,
            recargar=True,
        )
    if reserva is None and _franja_valida(inicio, fin):
        _alternativas(inicio, fin, int(asistentes), motivo, descartar=opciones[espacio])


def _franja_valida(inicio: datetime, fin: datetime) -> bool:
    """Las alternativas solo tienen sentido si el problema era el espacio, no la hora pedida."""
    try:
        reglas.validar_horario(inicio, fin, ahora=datetime.now())
    except NexoCampusError:
        return False
    return True


def _alternativas(inicio: datetime, fin: datetime, asistentes: int, motivo: str, descartar: str) -> None:
    """Si la reserva se rechazó, la IA ordena y explica los espacios que sí están libres en esa franja.

    Los candidatos salen de la base de datos; la IA no puede agregar espacios. Si falla, se muestran sin orden de IA.
    """
    from nexo_campus.ai.recomendaciones import recomendar_espacios
    from nexo_campus.repositories import reservas as repositorio

    libres = [e for e in repositorio.espacios_disponibles(inicio, fin, asistentes) if e.id != descartar]
    if not libres:
        st.caption("No hay otros espacios libres con ese aforo en esa franja.")
        return

    st.markdown(f"**Alternativas libres el {inicio:%d/%m} de {inicio:%H:%M} a {fin:%H:%M} para {asistentes} personas**")
    try:
        with st.spinner("Buscando la mejor alternativa con IA..."):
            recomendaciones = recomendar_espacios(motivo or "", asistentes, libres)
    except IAError as exc:
        st.caption(f"Sin recomendación de IA ({exc}). Se muestran ordenados del aforo más ajustado al más amplio.")
        recomendaciones = []

    por_id = {e.id: e for e in libres}
    if recomendaciones:
        ui.grilla(
            [
                ui.tarjeta_item(
                    f"{r.orden}. {por_id[r.espacio_id].nombre}",
                    [ui.badge("recomendada")] if r.orden == 1 else [],
                    [f"{r.espacio_id} · {ui.texto(por_id[r.espacio_id].tipo)} · Aforo {por_id[r.espacio_id].aforo}"],
                    r.razon,
                )
                for r in recomendaciones
            ],
            columnas=len(recomendaciones),
        )
        st.caption("Recomendación de la IA sobre espacios realmente libres. Elige uno en el formulario y vuelve a confirmar.")
        return
    ui.tabla(
        [
            {"Código": e.id, "Nombre": e.nombre, "Tipo": ui.texto(e.tipo), "Aforo": e.aforo, "Ubicación": e.ubicacion or "—"}
            for e in libres[:6]
        ],
        columnas_estado=(),
    )


def _reglas_vigentes() -> None:
    """Se leen de rules/reservas.py: si se cambia una constante, este panel lo refleja."""
    ui.lista_clave_valor(
        "Reglas vigentes",
        [
            ("Horario de reservas", f"{reglas.HORA_APERTURA:%H:%M} – {reglas.HORA_CIERRE:%H:%M}"),
            ("Duración mínima", f"{reglas.DURACION_MINIMA_MINUTOS} min"),
            ("Duración máxima", f"{reglas.DURACION_MAXIMA_HORAS} h"),
            ("Aforo", "No se puede superar"),
            ("Cruces de horario", "No permitidos"),
            ("Estados reservables", ", ".join(ui.etiqueta(e.value) for e in reglas.ESTADOS_RESERVABLES)),
            ("Incidencia alta o crítica", "Inhabilita el espacio"),
        ],
    )


def _reservas_registradas(espacios: list[Espacio]) -> None:
    from nexo_campus.repositories import reservas as repositorio
    from nexo_campus.services import reservas as servicio

    reservas = repositorio.listar_reservas()
    if not reservas:
        ui.estado_vacio("No hay reservas registradas", "Las reservas confirmadas aparecerán aquí.")
        return

    activas = {r.id: r for r in reservas if r.estado is EstadoReserva.activa}
    col_selector, col_boton = st.columns([4, 1], vertical_alignment="bottom")
    elegida = col_selector.selectbox(
        "Cancelar una reserva activa",
        list(activas),
        index=None,
        placeholder="Selecciona una reserva" if activas else "No hay reservas activas",
        format_func=lambda i: f"#{i} · {activas[i].espacio_id} · {activas[i].inicio:%d/%m %H:%M} · {activas[i].solicitante}",
        disabled=not activas,
    )
    if col_boton.button("Cancelar reserva", use_container_width=True, disabled=elegida is None):
        ui.ejecutar(lambda: servicio.cancelar_reserva(elegida), f"Reserva #{elegida} cancelada.", recargar=True)

    nombres = {e.id: e.nombre for e in espacios}
    # Regla central: una reserva activa a futuro en un espacio inhabilitado hay que reubicarla.
    inhabilitados = {e.id for e in espacios if e.estado is EstadoEspacio.inhabilitado}
    ahora = datetime.now()

    def aviso(r) -> str:
        if r.estado is EstadoReserva.activa and r.fin > ahora and r.espacio_id in inhabilitados:
            return "⛔ Reubicar: espacio inhabilitado"
        return ""

    por_reubicar = sum(bool(aviso(r)) for r in reservas)
    if por_reubicar:
        st.warning(
            f"{por_reubicar} reserva(s) activa(s) están en espacios inhabilitados por una incidencia. "
            "Cancélalas y créalas en otro espacio (al intentarlo, la IA recomienda alternativas).",
            icon="⛔",
        )
    ui.tabla(
        [
            {
                "#": r.id,
                "Espacio": f"{r.espacio_id} · {nombres.get(r.espacio_id, '')}",
                "Solicitante": r.solicitante,
                "Fecha": f"{r.inicio:%d/%m/%Y}",
                "Horario": f"{r.inicio:%H:%M} – {r.fin:%H:%M}",
                "Asistentes": r.asistentes,
                "Estado": ui.etiqueta(r.estado.value),
                "Aviso": aviso(r),
            }
            for r in sorted(reservas, key=lambda r: r.inicio)
        ],
        altura=400,
    )


def _catalogo(espacios: list[Espacio]) -> None:
    if not espacios:
        ui.estado_vacio("No hay espacios cargados", "Se mostrarán aquí después de cargar los datos oficiales.")
        return

    col_busqueda, col_tipo, col_estado = st.columns([2, 1, 1])
    busqueda = col_busqueda.text_input("Buscar", placeholder="Código o nombre", key="buscar_espacio")
    tipo = col_tipo.selectbox(
        "Tipo", ["Todos", *sorted({e.tipo for e in espacios})],
        format_func=ui.texto, key="tipo_espacio",
    )
    estado = col_estado.selectbox(
        "Estado", ["Todos", *sorted({e.estado.value for e in espacios})],
        format_func=lambda v: v if v == "Todos" else ui.etiqueta(v), key="estado_espacio",
    )

    texto = busqueda.strip().lower()
    filtrados = [
        e for e in espacios
        if (not texto or texto in e.id.lower() or texto in e.nombre.lower())
        and (tipo == "Todos" or e.tipo == tipo)
        and (estado == "Todos" or e.estado.value == estado)
    ]
    st.caption(f"{len(filtrados)} de {len(espacios)} espacios · los PCs de las salas de cómputo se prestan con la sala al reservarla")
    if filtrados:
        from nexo_campus.services import reservas as servicio

        ui.tabla(
            [
                {
                    "Código": e.id,
                    "Nombre": e.nombre,
                    "Tipo": ui.texto(e.tipo),
                    "Aforo": e.aforo,
                    "PCs": _texto_pcs(servicio.pcs_de_la_sala(e.id)) or "—",
                    "Ubicación": e.ubicacion or "—",
                    "Estado": ui.etiqueta(e.estado.value),
                }
                for e in filtrados
            ],
            altura=420,
        )


def _administrar(espacios: list[Espacio]) -> None:
    """Registrar espacios nuevos y editar los existentes (datos, aforo y estado)."""
    from nexo_campus.rules.catalogo import AFORO_MAXIMO
    from nexo_campus.services import catalogo as servicio

    estados = list(EstadoEspacio)
    col_nuevo, col_editar = st.columns(2)

    with col_nuevo:
        ui.seccion("Registrar un espacio")
        with st.form("form_nuevo_espacio", clear_on_submit=True):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código", placeholder="AU-101")
            nombre = c2.text_input("Nombre", placeholder="Aula 101")
            c3, c4 = st.columns(2)
            tipo = c3.text_input("Tipo", placeholder="aula, cubículo, laboratorio")
            aforo = c4.number_input("Aforo", min_value=1, max_value=AFORO_MAXIMO, value=20, step=1)
            ubicacion = st.text_input("Ubicación (opcional)", placeholder="Bloque A, piso 2")
            estado = st.selectbox("Estado", estados, format_func=lambda e: ui.etiqueta(e.value))
            if st.form_submit_button("Registrar espacio", type="primary"):
                ui.ejecutar(
                    lambda: servicio.crear_espacio(codigo, nombre, tipo, int(aforo), ubicacion, estado),
                    lambda e: f"Espacio {e.id} registrado.",
                    recargar=True,
                )

    with col_editar:
        ui.seccion("Editar un espacio")
        if not espacios:
            st.caption("Todavía no hay espacios para editar.")
            return
        opciones = {e.id: e for e in espacios}
        elegido = st.selectbox("Espacio", list(opciones), format_func=lambda i: f"{i} · {opciones[i].nombre}", key="editar_espacio")
        espacio = opciones[elegido]
        # La clave incluye el código: al cambiar de espacio, el formulario se llena con sus datos.
        with st.form(f"form_editar_espacio_{espacio.id}"):
            nombre = st.text_input("Nombre", value=espacio.nombre)
            c1, c2 = st.columns(2)
            tipo = c1.text_input("Tipo", value=ui.texto(espacio.tipo))
            aforo = c2.number_input("Aforo", min_value=1, max_value=AFORO_MAXIMO, value=min(espacio.aforo, AFORO_MAXIMO), step=1)
            ubicacion = st.text_input("Ubicación", value=espacio.ubicacion or "")
            estado = st.selectbox("Estado", estados, index=estados.index(espacio.estado), format_func=lambda e: ui.etiqueta(e.value))
            if st.form_submit_button("Guardar cambios", type="primary"):
                ui.ejecutar(
                    lambda: servicio.actualizar_espacio(espacio.id, nombre, tipo, int(aforo), ubicacion, estado),
                    f"Espacio {espacio.id} actualizado.",
                    recargar=True,
                )


def mostrar() -> None:
    espacios = catalogo.listar_espacios()
    repositorio_listo = ui.modulo_disponible(MODULO_REPOSITORIO)

    pestana_reservar, pestana_reservas, pestana_catalogo, pestana_admin = st.tabs(
        ["Reservar", "Reservas", f"Catálogo ({len(espacios)})", "Administrar"]
    )
    with pestana_admin:
        _administrar(espacios)

    with pestana_reservar:
        if not repositorio_listo:
            st.info("El formulario se activará cuando exista el repositorio de reservas (nexo_campus/repositories/reservas.py).", icon="🛠️")
        elif not espacios:
            st.info("Carga los datos oficiales para poder reservar espacios.", icon="📂")
        col_formulario, col_reglas = st.columns([2.2, 1])
        with col_formulario:
            _formulario_reserva(espacios, habilitado=repositorio_listo and bool(espacios))
        with col_reglas:
            _reglas_vigentes()

    with pestana_reservas:
        if repositorio_listo:
            _reservas_registradas(espacios)
        else:
            st.info("La lista de reservas se activará junto con el repositorio de reservas.", icon="🛠️")

    with pestana_catalogo:
        _catalogo(espacios)
