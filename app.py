"""Esqueleto de la interfaz: ejecutar con python -m streamlit run app.py."""

import streamlit as st


st.set_page_config(page_title="Nexo Campus", page_icon="🏫", layout="wide")

st.title("Nexo Campus")
st.caption("Gestión operativa de Campuslands · Interfaz en etapa inicial")

inicio, espacios, recursos, incidencias = st.tabs(
    ["Inicio", "Espacios", "Recursos", "Incidencias"]
)

with inicio:
    st.header("Inicio")
    st.write("Aquí se mostrará el resumen de la operación del campus.")

with espacios:
    st.header("Espacios")
    st.write("Aquí se mostrarán los espacios y las reservas.")

with recursos:
    st.header("Recursos")
    st.write("Aquí se mostrarán los equipos, los préstamos y las devoluciones.")

with incidencias:
    st.header("Incidencias")
    st.write("Aquí se mostrarán las incidencias y las solicitudes del campus.")
