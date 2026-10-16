"""Logo de Nexo Campus. Para cambiarlo, reemplaza ui/assets/logo.png (cuadrado, fondo transparente)."""

import base64
from pathlib import Path

import streamlit as st

RUTA_LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"


@st.cache_data
def logo_data_uri() -> str | None:
    """El logo embebido como data URI para usarlo en HTML. None si el archivo no existe."""
    if not RUTA_LOGO.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(RUTA_LOGO.read_bytes()).decode("ascii")
