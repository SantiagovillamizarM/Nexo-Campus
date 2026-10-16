"""Configuración central de Nexo Campus.

Lee las variables de entorno desde el archivo .env de la raíz del proyecto.
Ningún otro módulo debe leer os.environ directamente: todos importan desde aquí.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_ARCHIVO_ENV = BASE_DIR / ".env"
load_dotenv(_ARCHIVO_ENV)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"La variable {name} debe ser un número entero, se recibió '{value}'") from exc


# --- Datos y persistencia ---
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data/raw")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/nexo_campus.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# --- Inteligencia Artificial ---
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")
AI_MODELO_RESPALDO = os.getenv("AI_MODELO_RESPALDO", "")  # se usa si el principal agota su cuota
AI_TIMEOUT = _get_int("AI_TIMEOUT", 30)


def _fecha_env() -> float | None:
    try:
        return _ARCHIVO_ENV.stat().st_mtime
    except OSError:
        return None


_fecha_env_leida = _fecha_env()


def recargar_ia_si_cambio() -> None:
    """Si el .env cambió desde la última lectura, vuelve a leer la configuración de IA.

    Streamlit no reinicia la app al editar el .env: sin esto, cambiar la clave o pasar a
    Ollama exigiría cerrar y volver a abrir la aplicación.
    """
    global AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_MODELO_RESPALDO, AI_TIMEOUT, _fecha_env_leida
    fecha = _fecha_env()
    if fecha == _fecha_env_leida:
        return
    load_dotenv(_ARCHIVO_ENV, override=True)
    AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434/v1")
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "")
    AI_MODELO_RESPALDO = os.getenv("AI_MODELO_RESPALDO", "")
    AI_TIMEOUT = _get_int("AI_TIMEOUT", 30)
    _fecha_env_leida = fecha


def ai_configurada() -> bool:
    """Indica si hay un modelo de IA configurado en el .env (relee el archivo si cambió)."""
    recargar_ia_si_cambio()
    return bool(AI_MODEL and AI_BASE_URL)
