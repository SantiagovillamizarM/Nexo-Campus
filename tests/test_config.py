"""La configuración de IA se vuelve a leer cuando cambia el .env, sin reiniciar la app."""

import os

from nexo_campus import config


def test_relee_la_ia_cuando_cambia_el_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("AI_BASE_URL=http://localhost:11434/v1\nAI_MODEL=\n", encoding="utf-8")
    monkeypatch.setattr(config, "_ARCHIVO_ENV", env)
    monkeypatch.setattr(config, "_fecha_env_leida", None)
    for variable in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "AI_TIMEOUT"):
        monkeypatch.setattr(config, variable, getattr(config, variable))
        monkeypatch.delenv(variable, raising=False)

    assert config.ai_configurada() is False

    env.write_text("AI_BASE_URL=https://ia.local/v1\nAI_MODEL=modelo-nuevo\nAI_TIMEOUT=12\n", encoding="utf-8")
    os.utime(env, (env.stat().st_atime, env.stat().st_mtime + 5))  # asegura una fecha distinta
    assert config.ai_configurada() is True
    assert (config.AI_MODEL, config.AI_BASE_URL, config.AI_TIMEOUT) == ("modelo-nuevo", "https://ia.local/v1", 12)


def test_sin_cambios_no_pisa_valores_puestos_en_pruebas(monkeypatch):
    monkeypatch.setattr(config, "AI_MODEL", "modelo-de-prueba")
    config.ai_configurada()
    assert config.AI_MODEL == "modelo-de-prueba"
