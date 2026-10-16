"""Inicio: resumen de la operación y reporte de calidad de los datos oficiales."""

from collections import Counter

import streamlit as st

from nexo_campus.models import (
    EstadoEspacio,
    EstadoIncidencia,
    EstadoRecurso,
    Prioridad,
    RegistroInconsistente,
    TipoInconsistencia,
)
from nexo_campus.repositories import catalogo
from nexo_campus.ui import componentes as ui
from nexo_campus.ui.estilos import COLORES

TITULO = "Inicio"
DESCRIPCION = "Resumen de la operación del campus a partir de la información oficial."


def _resumen(espacios, recursos, incidencias, rechazados, advertencias) -> None:
    abiertas = [i for i in incidencias if i.estado is not EstadoIncidencia.cerrada]
    urgentes = sum(i.prioridad in (Prioridad.alta, Prioridad.critica) for i in abiertas)
    ui.fila_metricas(
        [
            ("Espacios", len(espacios), f"{sum(e.estado is EstadoEspacio.disponible for e in espacios)} disponibles", COLORES["primario"]),
            ("Recursos", len(recursos), f"{sum(r.estado is EstadoRecurso.disponible for r in recursos)} disponibles", COLORES["info"]),
            ("Incidencias abiertas", len(abiertas), f"{urgentes} de prioridad alta o crítica", COLORES["alerta"]),
            ("Registros rechazados", len(rechazados), f"{len(advertencias)} advertencias en la carga", COLORES["peligro"]),
        ]
    )

    col_espacios, col_recursos, col_incidencias = st.columns(3)
    with col_espacios:
        ui.barras_distribucion("Espacios por estado", Counter(e.estado.value for e in espacios), [s.value for s in EstadoEspacio])
    with col_recursos:
        ui.barras_distribucion("Recursos por estado", Counter(r.estado.value for r in recursos), [s.value for s in EstadoRecurso])
    with col_incidencias:
        ui.barras_distribucion(
            "Incidencias abiertas por prioridad",
            Counter(i.prioridad.value for i in abiertas if i.prioridad),
            [p.value for p in reversed(Prioridad)],
        )


def _filas(registros: list[RegistroInconsistente]) -> list[dict]:
    return [
        {
            "Entidad": r.entidad.capitalize(),
            "Archivo": r.archivo or "—",
            "Fila": str(r.fila) if r.fila else "Archivo",
            "ID": r.identificador or "—",
            "Motivo": r.motivo,
        }
        for r in registros
    ]


def _calidad(inconsistencias, rechazados, advertencias) -> None:
    if not inconsistencias:
        st.caption("El reporte aparecerá después de la primera carga de datos.")
        return

    col_resumen, col_detalle = st.columns([1, 3])
    with col_resumen:
        ui.barras_distribucion(
            "Problemas por entidad",
            Counter(i.entidad for i in inconsistencias),
            sorted({i.entidad for i in inconsistencias}),
        )
    with col_detalle:
        tipo = st.radio(
            "Tipo",
            ["rechazados", "advertencias"],
            format_func=lambda t: f"Rechazados ({len(rechazados)})" if t == "rechazados" else f"Advertencias ({len(advertencias)})",
            horizontal=True,
            label_visibility="collapsed",
            key="tipo_inconsistencia",
        )
        registros = rechazados if tipo == "rechazados" else advertencias
        if registros:
            ui.tabla(_filas(registros), columnas_estado=(), altura=380)
        else:
            st.caption("No hay registros de este tipo.")


def _cargar_datos() -> None:
    """Las personas de Campuslands suben los archivos oficiales y se cargan con la validación de siempre."""
    from nexo_campus.carga import importacion
    from nexo_campus.carga.cargador import ENTIDADES

    col_subida, col_ayuda = st.columns([2.2, 1])
    with col_ayuda:
        ui.lista_clave_valor(
            "Qué se puede cargar",
            [
                ("Formatos", "CSV, Excel o JSON"),
                ("Espacios", "código, nombre, aforo"),
                ("Recursos", "código, nombre"),
                ("Reservas", "espacio, solicitante, inicio, fin, asistentes"),
                ("Préstamos", "equipo, solicitante, fecha"),
                ("Incidencias", "descripción"),
            ],
        )
    with col_subida:
        archivos = st.file_uploader(
            "Archivos oficiales de Campuslands", type=["csv", "xlsx", "xls", "json"],
            accept_multiple_files=True, key="archivos_oficiales",
        )
        if not archivos:
            st.caption("Sube uno o varios archivos. Cada registro se valida y lo que no cumpla queda en el reporte de calidad.")
            return

        asignacion = []
        for archivo in archivos:
            col_nombre, col_tipo = st.columns([2, 1], vertical_alignment="center")
            col_nombre.markdown(f"**{archivo.name}** · {archivo.size / 1024:,.0f} KB")
            sugerida = importacion.adivinar_entidad(archivo.name)
            entidad = col_tipo.selectbox(
                f"Contenido de {archivo.name}", ENTIDADES,
                index=ENTIDADES.index(sugerida) if sugerida else None, placeholder="¿Qué contiene?",
                format_func=str.capitalize, label_visibility="collapsed", key=f"entidad_{archivo.file_id}",
            )
            asignacion.append((entidad, archivo))

        reemplazar = True
        if importacion.hay_datos_cargados():
            reemplazar = st.checkbox(
                "Reemplazar la información actual (también se borran las reservas, préstamos e incidencias registradas desde la aplicación)",
                key="reemplazar_datos",
            )
        if not st.button("Validar y cargar", type="primary", disabled=not reemplazar):
            return

        entidades = [entidad for entidad, _ in asignacion]
        if None in entidades:
            st.error("Indica qué contiene cada archivo.", icon="⚠️")
            return
        repetidas = sorted({e for e in entidades if entidades.count(e) > 1})
        if repetidas:
            st.error(f"Hay más de un archivo para: {', '.join(repetidas)}. Deja uno por tipo de datos.", icon="⚠️")
            return

        with st.spinner("Validando y cargando los datos..."):
            ui.ejecutar(
                lambda: importacion.importar_archivos(
                    {entidad: (archivo.name, archivo.getvalue()) for entidad, archivo in asignacion}, reemplazar=reemplazar
                ),
                lambda reporte: (
                    f"Datos cargados: {reporte.total_cargados} registros válidos, {reporte.total_rechazados} rechazados. "
                    "Revisa el detalle en Calidad de datos."
                ),
                recargar=True,
            )


def mostrar() -> None:
    espacios = catalogo.listar_espacios()
    recursos = catalogo.listar_recursos()
    incidencias = catalogo.listar_incidencias()
    inconsistencias = catalogo.listar_inconsistencias()
    rechazados = [i for i in inconsistencias if i.tipo is TipoInconsistencia.rechazado]
    advertencias = [i for i in inconsistencias if i.tipo is TipoInconsistencia.advertencia]

    if not (espacios or recursos or incidencias):
        ui.estado_vacio(
            "Todavía no hay datos cargados",
            "Sube los archivos oficiales en la pestaña <code>Cargar datos</code> o ejecuta "
            "<code>python scripts/cargar_datos.py</code>.",
        )

    pestana_resumen, pestana_calidad, pestana_carga = st.tabs(
        ["Resumen", f"Calidad de datos ({len(inconsistencias)})", "Cargar datos"]
    )
    with pestana_resumen:
        _resumen(espacios, recursos, incidencias, rechazados, advertencias)
    with pestana_calidad:
        _calidad(inconsistencias, rechazados, advertencias)
    with pestana_carga:
        _cargar_datos()
