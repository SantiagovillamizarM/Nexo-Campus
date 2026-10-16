"""Piezas visuales reutilizables. Las pantallas solo combinan estas funciones."""

import html
import importlib.util
import logging
from collections.abc import Callable, Mapping
from datetime import date
from typing import TypeVar

import pandas as pd
import streamlit as st

from nexo_campus import config
from nexo_campus.errors import NexoCampusError
from nexo_campus.ui.estilos import COLORES

Resultado = TypeVar("Resultado")
log = logging.getLogger(__name__)

# valor guardado en la base -> (texto para el usuario, color)
ESTADOS = {
    "disponible": ("Disponible", COLORES["exito"]),
    "activa": ("Activa", COLORES["exito"]),
    "activo": ("Activo", COLORES["exito"]),
    "prestado": ("Prestado", COLORES["info"]),
    "en_proceso": ("En proceso", COLORES["info"]),
    "abierta": ("Abierta", COLORES["alerta"]),
    "mantenimiento": ("Mantenimiento", COLORES["alerta"]),
    "danado": ("Dañado", COLORES["peligro"]),
    "inhabilitado": ("Inhabilitado", COLORES["peligro"]),
    "cancelada": ("Cancelada", COLORES["tenue"]),
    "cerrada": ("Cerrada", COLORES["tenue"]),
    "devuelto": ("Devuelto", COLORES["tenue"]),
    "baja": ("Baja", COLORES["tenue"]),
    "media": ("Media", COLORES["info"]),
    "alta": ("Alta", COLORES["alerta"]),
    "critica": ("Crítica", COLORES["peligro"]),
    "ia": ("Clasificada por IA", COLORES["primario_claro"]),
    "manual": ("Clasificación manual", COLORES["tenue"]),
    "datos_origen": ("Datos de origen", COLORES["info"]),
    # Origen de un cambio de estado en el historial de recursos
    "carga": ("Carga de datos", COLORES["tenue"]),
    "prestamo": ("Préstamo", COLORES["info"]),
    "devolucion": ("Devolución", COLORES["exito"]),
    "incidencia": ("Incidencia", COLORES["alerta"]),
    "edicion": ("Edición manual", COLORES["primario_claro"]),
    "recomendada": ("Mejor opción según la IA", COLORES["primario_claro"]),
}
_COLOR_POR_ETIQUETA = {texto: color for texto, color in ESTADOS.values()}

# Claves del dominio que necesitan tildes o mayúsculas al mostrarse
_TEXTOS = {
    "tecnologia": "Tecnología",
    "soporte_ti": "Soporte TI",
    "bienestar_estudiantil": "Bienestar estudiantil",
    "servicios_generales": "Servicios generales",
    "cubiculo": "Cubículo",
    "otro": "Otro",
    "portatil": "Portátil",
}

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

_CLAVE_AVISO = "nc_aviso_pendiente"


def escapar(valor: object) -> str:
    """Todo texto que viene de los datos se escapa antes de meterlo en HTML."""
    return "" if valor is None else html.escape(str(valor))


def _html(contenido: str) -> None:
    # Markdown interpreta las líneas con sangría como bloques de código: se quita antes de dibujar.
    st.markdown("".join(linea.strip() for linea in contenido.splitlines()), unsafe_allow_html=True)


def _rgba(color_hex: str, opacidad: float) -> str:
    r, g, b = (int(color_hex[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {opacidad})"


def modulo_disponible(nombre: str) -> bool:
    """Indica si un módulo del backend ya existe, para activar la pantalla que lo usa."""
    try:
        return importlib.util.find_spec(nombre) is not None
    except ModuleNotFoundError:
        return False


def texto(clave: str | None) -> str:
    """Convierte una clave del dominio en texto legible: 'soporte_ti' -> 'Soporte TI'."""
    if not clave:
        return "—"
    return _TEXTOS.get(clave, clave.replace("_", " ").capitalize())


def etiqueta(valor: str | None) -> str:
    if valor is None:
        return "—"
    return ESTADOS.get(valor, (valor.replace("_", " ").capitalize(), ""))[0]


def badge(valor: str | None) -> str:
    if valor is None:
        return ""
    texto, color = ESTADOS.get(valor, (valor.replace("_", " ").capitalize(), COLORES["tenue"]))
    return f'<span class="nc-badge" style="background:{_rgba(color, .12)};color:{color}">{escapar(texto)}</span>'


# --- Menú lateral y encabezado ------------------------------------------------------------------


def marca() -> None:
    _html(
        """
        <div class="nc-marca">
          <div class="nc-logo">N</div>
          <div>
            <div class="nc-marca-nombre">Nexo Campus</div>
            <div class="nc-marca-detalle">Gestión operativa · Campuslands</div>
          </div>
        </div>
        <div class="nc-menu-titulo">Módulos</div>
        """
    )


def estado_sistema(hay_datos: bool) -> None:
    color_datos = COLORES["exito"] if hay_datos else COLORES["alerta"]
    texto_datos = "Datos oficiales cargados" if hay_datos else "Sin datos cargados"
    if config.ai_configurada():
        color_ia, texto_ia = COLORES["exito"], f"IA activa · {escapar(config.AI_MODEL)}"
    else:
        color_ia, texto_ia = COLORES["tenue"], "IA sin configurar"
    _html(
        f"""
        <div class="nc-sistema">
          <div class="nc-menu-titulo">Estado del sistema</div>
          <div class="nc-sistema-fila"><span class="nc-dot" style="background:{color_datos}"></span>{texto_datos}</div>
          <div class="nc-sistema-fila"><span class="nc-dot" style="background:{color_ia}"></span>{texto_ia}</div>
        </div>
        """
    )


def encabezado_pagina(titulo: str, descripcion: str) -> None:
    hoy = date.today()
    fecha = f"{_DIAS[hoy.weekday()].capitalize()}, {hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}"
    _html(
        f"""
        <div class="nc-pagina">
          <div><h1>{escapar(titulo)}</h1><p>{escapar(descripcion)}</p></div>
          <div class="nc-fecha">{fecha}</div>
        </div>
        """
    )


def seccion(titulo: str, subtitulo: str | None = None) -> None:
    detalle = f"<p>{escapar(subtitulo)}</p>" if subtitulo else ""
    _html(f'<div class="nc-section"><h3>{escapar(titulo)}</h3>{detalle}</div>')


def estado_vacio(titulo: str, mensaje_html: str) -> None:
    """mensaje_html es texto fijo del código (puede llevar <code>), nunca datos del usuario."""
    _html(f'<div class="nc-empty"><div class="nc-empty-icon">✦</div><h4>{escapar(titulo)}</h4><p>{mensaje_html}</p></div>')


# --- Tarjetas y listas ---------------------------------------------------------------------------


def tarjeta_metrica(titulo: str, valor: int | str, detalle: str, color: str) -> None:
    _html(
        f"""
        <div class="nc-card nc-metrica" style="--nc-color:{color}">
          <div class="nc-metric-label">{escapar(titulo)}</div>
          <div class="nc-metric-value">{escapar(valor)}</div>
          <div class="nc-metric-detail">{escapar(detalle)}</div>
        </div>
        """
    )


def fila_metricas(metricas: list[tuple[str, int | str, str, str]]) -> None:
    """Una fila de tarjetas de métricas: (título, valor, detalle, color)."""
    for columna, (titulo, valor, detalle, color) in zip(st.columns(len(metricas)), metricas):
        with columna:
            tarjeta_metrica(titulo, valor, detalle, color)


def tarjeta_item(titulo: str, badges: list[str], meta: list[str], texto: str | None = None) -> str:
    """Devuelve el HTML de una tarjeta (se usa para incidencias)."""
    meta_html = "".join(f'<div class="nc-item-meta">{escapar(linea)}</div>' for linea in meta if linea)
    texto_html = f'<div class="nc-item-text">{escapar(texto)}</div>' if texto else ""
    return f"""
        <div class="nc-card">
          <div class="nc-item-top">
            <div class="nc-item-title">{escapar(titulo)}</div>
            <div class="nc-badges">{"".join(badges)}</div>
          </div>
          {texto_html}{meta_html}
        </div>
    """


def grilla(tarjetas: list[str], columnas: int = 3) -> None:
    cols = st.columns(columnas)
    for posicion, tarjeta in enumerate(tarjetas):
        with cols[posicion % columnas]:
            _html(tarjeta)


def barras_distribucion(titulo: str, conteo: Mapping[str, int], orden: list[str]) -> None:
    """Tarjeta con una barra por valor, en el orden indicado, con cantidad y porcentaje."""
    total = sum(conteo.values())
    if total == 0:
        filas = '<div class="nc-item-meta">Sin registros todavía.</div>'
    else:
        partes = []
        for valor in orden:
            cantidad = conteo.get(valor, 0)
            porcentaje = round(cantidad * 100 / total)
            color = ESTADOS.get(valor, ("", COLORES["tenue"]))[1]
            partes.append(
                f'<div class="nc-bar-row"><span>{escapar(etiqueta(valor))}</span><span>{cantidad} · {porcentaje}%</span></div>'
                f'<div class="nc-bar"><span style="width:{porcentaje}%;background:{color}"></span></div>'
            )
        filas = "".join(partes)
    _html(f'<div class="nc-card"><div class="nc-section"><h3>{escapar(titulo)}</h3></div>{filas}</div>')


def lista_clave_valor(titulo: str, filas: list[tuple[str, str]]) -> None:
    """Tarjeta con pares etiqueta / valor (ej. las reglas vigentes)."""
    items = "".join(f"<li><span>{escapar(k)}</span><span>{escapar(v)}</span></li>" for k, v in filas)
    _html(f'<div class="nc-card"><div class="nc-section"><h3>{escapar(titulo)}</h3></div><ul class="nc-reglas">{items}</ul></div>')


def tabla(filas: list[dict], columnas_estado: tuple[str, ...] = ("Estado",), altura: int | None = None) -> None:
    """Tabla con las columnas de estado coloreadas. La altura fija evita alargar la página."""
    datos = pd.DataFrame(filas)

    def colorear(valor: object) -> str:
        color = _COLOR_POR_ETIQUETA.get(str(valor))
        return f"color: {color}; font-weight: 600" if color else ""

    presentes = [c for c in columnas_estado if c in datos.columns]
    contenido = datos.style.map(colorear, subset=presentes) if presentes else datos
    st.dataframe(contenido, hide_index=True, use_container_width=True, height=altura)


# --- Acciones con manejo de errores --------------------------------------------------------------


def ejecutar(
    accion: Callable[[], Resultado],
    mensaje_exito: str | Callable[[Resultado], str],
    recargar: bool = False,
) -> Resultado | None:
    """Ejecuta una acción del backend y muestra el resultado sin dejar escapar excepciones.

    mensaje_exito puede ser un texto o una función que arma el texto a partir del resultado.
    Con recargar=True la página se vuelve a dibujar (para refrescar tablas) y el mensaje
    de éxito se muestra después de recargar.
    """
    try:
        resultado = accion()
    except NexoCampusError as exc:
        st.error(str(exc), icon="⚠️")
        return None
    except Exception:
        log.exception("Error inesperado en la interfaz")
        st.error("Ocurrió un error inesperado. Intenta de nuevo; si persiste, revisa la consola.", icon="🚨")
        return None

    mensaje = mensaje_exito(resultado) if callable(mensaje_exito) else mensaje_exito
    if recargar:
        st.session_state[_CLAVE_AVISO] = mensaje
        st.rerun()
    st.success(mensaje, icon="✅")
    return resultado


def mostrar_aviso_pendiente() -> None:
    mensaje = st.session_state.pop(_CLAVE_AVISO, None)
    if mensaje:
        st.toast(mensaje, icon="✅")
