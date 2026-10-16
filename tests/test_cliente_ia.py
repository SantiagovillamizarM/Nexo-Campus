"""Errores del servicio de IA convertidos en mensajes claros (sin llamar a la API real)."""

import httpx
import openai
import pytest

from nexo_campus.ai import cliente
from nexo_campus.errors import IAError


def _error(clase, codigo: int):
    respuesta = httpx.Response(codigo, request=httpx.Request("POST", "https://ia.local/chat/completions"))
    return clase("error simulado", response=respuesta, body=None)


class ServicioFalso:
    """Imita client.chat.completions.create: lanza los errores indicados y luego responde."""

    def __init__(self, *errores):
        self.errores = list(errores)
        self.llamadas = 0
        self.modelos: list[str] = []
        self.chat = self
        self.completions = self

    def create(self, **datos):
        self.llamadas += 1
        self.modelos.append(datos["model"])
        if self.errores:
            raise self.errores.pop(0)
        mensaje = type("Mensaje", (), {"content": "hola"})()
        return type("Respuesta", (), {"choices": [type("Opcion", (), {"message": mensaje})()]})()


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(cliente, "ESPERA_LIMITE_SEGUNDOS", 0)
    monkeypatch.setattr(cliente.config, "AI_MODEL", "modelo-principal")
    monkeypatch.setattr(cliente.config, "AI_MODELO_RESPALDO", "")

    def instalar(*errores):
        falso = ServicioFalso(*errores)
        monkeypatch.setattr(cliente, "_crear_cliente", lambda: falso)
        return falso

    return instalar


def test_limite_de_consultas_se_reintenta_una_vez(servicio):
    falso = servicio(_error(openai.RateLimitError, 429))
    assert cliente.consultar_texto("hola") == "hola"
    assert falso.llamadas == 2


def test_limite_persistente_da_mensaje_claro(servicio):
    falso = servicio(_error(openai.RateLimitError, 429), _error(openai.RateLimitError, 429))
    with pytest.raises(IAError, match="límite de consultas"):
        cliente.consultar_texto("hola")
    assert falso.llamadas == 2


@pytest.mark.parametrize(
    ("clase", "codigo", "mensaje"),
    [
        (openai.AuthenticationError, 401, "clave de la IA no es válida"),
        (openai.PermissionDeniedError, 403, "clave de la IA no es válida"),
        (openai.NotFoundError, 404, "no existe en el servicio"),
        (openai.InternalServerError, 500, r"error \(500\)"),
    ],
)
def test_errores_del_servicio(servicio, clase, codigo, mensaje):
    servicio(_error(clase, codigo))
    with pytest.raises(IAError, match=mensaje):
        cliente.consultar_texto("hola")


def test_sin_cuota_usa_el_modelo_de_respaldo(servicio, monkeypatch):
    monkeypatch.setattr(cliente.config, "AI_MODELO_RESPALDO", "modelo-respaldo")
    falso = servicio(_error(openai.RateLimitError, 429))
    assert cliente.consultar_texto("hola") == "hola"
    assert falso.modelos == ["modelo-principal", "modelo-respaldo"]


def test_si_el_respaldo_tambien_se_agota_da_mensaje_claro(servicio, monkeypatch):
    monkeypatch.setattr(cliente.config, "AI_MODELO_RESPALDO", "modelo-respaldo")
    servicio(_error(openai.RateLimitError, 429), _error(openai.RateLimitError, 429))
    with pytest.raises(IAError, match="cuota diaria"):
        cliente.consultar_texto("hola")
