"""Cliente de IA compatible con la API de OpenAI (Ollama local u otro proveedor autorizado).

Toda la configuración sale de nexo_campus.config. Cualquier fallo se convierte en IAError
para que la UI muestre un mensaje claro y permita clasificar a mano.
"""

import json
import time
from typing import TypeVar

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from nexo_campus import config
from nexo_campus.errors import IAError

ModeloRespuesta = TypeVar("ModeloRespuesta", bound=BaseModel)
ESPERA_LIMITE_SEGUNDOS = 4  # pausa antes del único reintento cuando el servicio limita las consultas


def _crear_cliente() -> OpenAI:
    if not config.ai_configurada():
        raise IAError("La IA no está configurada. Revisa AI_BASE_URL y AI_MODEL en el archivo .env.")
    # Ollama ignora la clave, pero el cliente de openai exige un valor no vacío.
    return OpenAI(
        base_url=config.AI_BASE_URL,
        api_key=config.AI_API_KEY or "sin-clave",
        timeout=config.AI_TIMEOUT,
        max_retries=0,
    )


def _completar(mensajes: list[dict[str, str]], formato_json: bool) -> str:
    extra = {"response_format": {"type": "json_object"}} if formato_json else {}

    def pedir():
        return _crear_cliente().chat.completions.create(
            model=config.AI_MODEL,
            messages=mensajes,
            temperature=0,
            **extra,
        )

    try:
        try:
            respuesta = pedir()
        except openai.RateLimitError:
            # El plan gratuito de Gemini limita las consultas por minuto: se reintenta una sola vez.
            time.sleep(ESPERA_LIMITE_SEGUNDOS)
            respuesta = pedir()
    except openai.APITimeoutError as exc:
        raise IAError(f"La IA no respondió en {config.AI_TIMEOUT} segundos.") from exc
    except openai.APIConnectionError as exc:
        raise IAError("No se pudo conectar con el servicio de IA. Verifica la conexión a internet o que el servicio esté en ejecución.") from exc
    except openai.RateLimitError as exc:
        raise IAError("Se alcanzó el límite de consultas a la IA. Espera un minuto e intenta de nuevo.") from exc
    except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
        raise IAError("La clave de la IA no es válida o no tiene permisos. Revisa AI_API_KEY en el archivo .env.") from exc
    except openai.NotFoundError as exc:
        raise IAError(f"El modelo '{config.AI_MODEL}' no existe en el servicio de IA. Revisa AI_MODEL en el archivo .env.") from exc
    except openai.APIStatusError as exc:
        raise IAError(f"El servicio de IA devolvió un error ({exc.status_code}).") from exc

    contenido = respuesta.choices[0].message.content
    if not contenido:
        raise IAError("La IA devolvió una respuesta vacía.")
    return contenido


def consultar_texto(mensaje: str, instrucciones: str = "") -> str:
    """Envía un mensaje a la IA y devuelve su respuesta como texto libre."""
    mensajes = [{"role": "system", "content": instrucciones}] if instrucciones else []
    mensajes.append({"role": "user", "content": mensaje})
    return _completar(mensajes, formato_json=False)


def consultar_json(
    mensaje: str, instrucciones: str, modelo: type[ModeloRespuesta]
) -> ModeloRespuesta:
    """Pide a la IA una respuesta JSON y la valida con el modelo Pydantic indicado."""
    mensajes = [
        {"role": "system", "content": instrucciones},
        {"role": "user", "content": mensaje},
    ]
    contenido = _completar(mensajes, formato_json=True)
    try:
        return modelo.model_validate(json.loads(contenido))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise IAError("La IA devolvió una respuesta con un formato inválido.") from exc
