"""Recomendación de espacios alternativos con IA.

La IA solo ordena y explica: los candidatos salen de la base de datos (espacios_disponibles del
repositorio de reservas). Si la IA devuelve un espacio que no está entre los candidatos, se descarta.
"""

from pydantic import BaseModel, field_validator

from nexo_campus.ai.cliente import consultar_json
from nexo_campus.errors import IAError
from nexo_campus.models import Espacio

MAX_RECOMENDACIONES = 3
MAX_CANDIDATOS_EN_PROMPT = 15  # el modelo local pierde precisión con listas muy largas

INSTRUCCIONES = f"""Eres el asistente de reservas de Campuslands, un campus educativo.
Una reserva no se pudo hacer y debes recomendar espacios alternativos.
Recibes el motivo de la reserva, el número de asistentes y una lista de espacios CANDIDATOS que ya están
libres y tienen aforo suficiente. Devuelve {MAX_RECOMENDACIONES} recomendaciones (o todos los candidatos si hay
menos), ordenadas del más adecuado (orden 1) al menos adecuado.

Criterios:
- El tipo de espacio debe servir para el motivo (una clase necesita un aula o laboratorio; una reunión
  pequeña o una asesoría cabe en un cubículo).
- Prefiere el aforo más ajustado a los asistentes, sin desperdiciar espacios grandes.
- Cada razón es UNA frase corta (máximo 15 palabras) basada solo en el tipo y el aforo del candidato.

Responde SOLO con un objeto JSON así (ejemplo con tres recomendaciones):
{{"recomendaciones": [
  {{"espacio_id": "<id de la lista>", "razon": "<por qué es la mejor opción>", "orden": 1}},
  {{"espacio_id": "<otro id de la lista>", "razon": "<por qué es la segunda opción>", "orden": 2}},
  {{"espacio_id": "<otro id de la lista>", "razon": "<por qué es la tercera opción>", "orden": 3}}
]}}

Usa SOLO los espacio_id que aparecen en la lista de candidatos, escritos exactamente igual. No inventes espacios."""


class Recomendacion(BaseModel):
    """Un espacio sugerido por la IA, con su razón y su posición (1 = el mejor)."""

    espacio_id: str
    razon: str
    orden: int

    @field_validator("espacio_id", "razon")
    @classmethod
    def _sin_espacios(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el campo está vacío")
        return valor


class _RespuestaRecomendaciones(BaseModel):
    recomendaciones: list[Recomendacion]


def _describir_candidatos(candidatos: list[Espacio]) -> str:
    return "\n".join(
        f"- espacio_id: {e.id} | {e.nombre} | tipo {e.tipo} | aforo {e.aforo} | ubicación {e.ubicacion or 'sin dato'}"
        for e in candidatos
    )


def recomendar_espacios(motivo: str, asistentes: int, candidatos: list[Espacio]) -> list[Recomendacion]:
    """Pide a la IA que ordene los candidatos y devuelve solo los que existen en la lista.

    Sin candidatos devuelve una lista vacía sin llamar a la IA. Lanza IAError si la IA falla
    o si ninguna de sus recomendaciones es un candidato válido.
    """
    if not candidatos:
        return []
    candidatos = candidatos[:MAX_CANDIDATOS_EN_PROMPT]
    mensaje = (
        f"Motivo de la reserva: {motivo.strip() or 'sin motivo indicado'}\n"
        f"Asistentes: {asistentes}\n"
        f"Candidatos:\n{_describir_candidatos(candidatos)}"
    )
    respuesta = consultar_json(mensaje, INSTRUCCIONES, _RespuestaRecomendaciones)

    ids_validos = {e.id for e in candidatos}
    vistas: set[str] = set()
    validas = []
    for recomendacion in sorted(respuesta.recomendaciones, key=lambda r: r.orden):
        if recomendacion.espacio_id in ids_validos and recomendacion.espacio_id not in vistas:
            vistas.add(recomendacion.espacio_id)
            validas.append(recomendacion)
    if not validas:
        raise IAError("La IA no recomendó ningún espacio de la lista de disponibles.")

    # Se renumera porque pueden haberse descartado recomendaciones inventadas o repetidas.
    return [
        r.model_copy(update={"orden": posicion})
        for posicion, r in enumerate(validas[:MAX_RECOMENDACIONES], start=1)
    ]
