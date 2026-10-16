"""Configuración central de Nexo Campus.

Lee las variables de entorno desde el archivo .env de la raíz del proyecto.
Ningún otro módulo debe leer os.environ directamente: todos importan desde aquí.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


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
AI_TIMEOUT = _get_int("AI_TIMEOUT", 30)


def ai_configurada() -> bool:
    """Indica si hay un modelo de IA configurado en el .env."""
    return bool(AI_MODEL and AI_BASE_URL)
