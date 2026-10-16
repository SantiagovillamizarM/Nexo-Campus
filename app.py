"""Punto de entrada de la interfaz: python -m streamlit run app.py"""

import sys
from pathlib import Path

import streamlit as st

# Garantiza que el paquete nexo_campus se encuentre sin importar desde qué carpeta se ejecute.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nexo_campus import db  # noqa: E402
from nexo_campus.repositories import catalogo  # noqa: E402
from nexo_campus.ui import componentes as ui  # noqa: E402
from nexo_campus.ui import espacios, incidencias, inicio, recursos  # noqa: E402
from nexo_campus.ui.estilos import aplicar_estilos  # noqa: E402

# Cada módulo de la interfaz expone TITULO, DESCRIPCION y mostrar()
PAGINAS = {modulo.TITULO: modulo for modulo in (inicio, espacios, recursos, incidencias)}

st.set_page_config(page_title="Nexo Campus", page_icon="✦", layout="wide", initial_sidebar_state="expanded")
aplicar_estilos()
db.crear_tablas()  # crea las tablas vacías si la base todavía no existe; no borra nada

with st.sidebar:
    ui.marca()
    seleccion = st.radio("Módulos", list(PAGINAS), label_visibility="collapsed", key="pagina")
    ui.estado_sistema(hay_datos=bool(catalogo.listar_espacios() or catalogo.listar_recursos()))

ui.mostrar_aviso_pendiente()
pagina = PAGINAS[seleccion]
ui.encabezado_pagina(pagina.TITULO, pagina.DESCRIPCION)
pagina.mostrar()
