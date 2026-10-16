"""Triaje de incidencias con IA: categoría, prioridad, área responsable y justificación.

La respuesta de la IA se valida contra las listas fijas de este archivo. Si la IA inventa
una categoría o un área fuera de la lista, se trata como IAError (nunca se acepta en silencio).
"""

import unicodedata

from pydantic import BaseModel, field_validator, model_validator

from nexo_campus.ai.cliente import consultar_json
from nexo_campus.errors import NexoCampusError
from nexo_campus.models import Prioridad

# Cada categoría se enruta a un área fija. La IA propone ambas y aquí se verifica que coincidan.
AREA_POR_CATEGORIA = {
    "infraestructura": "mantenimiento",
    "tecnologia": "soporte_ti",
    "aseo": "servicios_generales",
    "seguridad": "seguridad",
    "bienestar": "bienestar_estudiantil",
}
CATEGORIAS = tuple(AREA_POR_CATEGORIA)
AREAS_RESPONSABLES = tuple(AREA_POR_CATEGORIA.values())
MAX_CARACTERES_INCIDENCIA = 1000

INSTRUCCIONES = f"""Eres el sistema de triaje de incidencias de Campuslands, un campus educativo.
Lees el reporte de una persona y lo clasificas. Responde SOLO con un objeto JSON con estas claves, en este orden:

1. "justificacion": una frase en español que diga cuál es el problema real y qué tan urgente es. No copies el reporte.
2. "categoria": una de {list(CATEGORIAS)}
    seguridad = algo o alguien pone en riesgo a las personas o sus cosas: robos, hurtos, extraños sospechosos,
                peleas, agresiones, humo, fuego, chispas, olor a quemado, cables pelados.
    bienestar = la salud o el estado emocional de una persona: desmayo, herida, dolor, crisis, estrés,
                ansiedad, acoso, burlas, discriminación, conflictos de convivencia.
    tecnologia = fallas de computadores, portátiles, proyectores, red, wifi, software, plataformas o cuentas.
    infraestructura = daños del edificio o sus instalaciones: energía eléctrica, apagones, luces, aire
                acondicionado, puertas, sillas, mesas, goteras, tuberías, baños dañados.
    aseo = SOLO suciedad o limpieza: basura, derrames, malos olores, falta de papel o jabón.
  Clasifica por el PROBLEMA, no por el objeto ni por el lugar: si roban un portátil es seguridad (no tecnologia);
  si un cable hace chispas es seguridad (no tecnologia); si alguien se desmaya es bienestar (no seguridad).
  Usa aseo únicamente cuando el problema sea de limpieza.
3. "prioridad": una de {[p.value for p in Prioridad]}
    critica = hay peligro AHORA para la vida o la salud: humo, fuego, chispas, olor a quemado, peleas a golpes,
              persona desmayada, herida o con dificultad para respirar, inundación. Las chispas siempre son critica.
    alta = algo NO FUNCIONA EN ABSOLUTO (no enciende, no hay luz, no hay internet) y eso impide usar un espacio
           o equipo, o afecta a un grupo completo o a todo un piso o bloque; también un robo, un extraño
           sospechoso, acoso, o una persona que pide ayuda emocional.
    media = algo funciona MAL pero se puede seguir trabajando (aire acondicionado que no enfría, computador
            lento o que se reinicia, gotera, basura acumulada).
    baja = solicitud menor o estética, sin urgencia (falta papel, un derrame pequeño, una silla floja).
4. "area_responsable": se deduce de la categoría, siempre así:
    {", ".join(f"{c} -> {a}" for c, a in AREA_POR_CATEGORIA.items())}.

Ejemplos:
Reporte: "La puerta del aula 305 no cierra"
{{"justificacion": "La puerta es parte de las instalaciones del aula; el aula se puede usar, pero no se puede asegurar.", "categoria": "infraestructura", "prioridad": "media", "area_responsable": "mantenimiento"}}
Reporte: "Alguien abrió mi casillero y se llevó mi celular"
{{"justificacion": "Es un hurto dentro del campus y requiere atención pronta de seguridad.", "categoria": "seguridad", "prioridad": "alta", "area_responsable": "seguridad"}}
Reporte: "Una estudiante se cortó la mano con un vidrio en el taller"
{{"justificacion": "Una persona está herida y necesita atención de salud inmediata.", "categoria": "bienestar", "prioridad": "critica", "area_responsable": "bienestar_estudiantil"}}

Usa exactamente los valores de las listas, en minúsculas y sin tildes. No agregues otras claves."""


def _normalizar(valor: str) -> str:
    """Pasa a minúsculas y quita tildes y espacios, para comparar con las listas fijas."""
    sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.strip().lower().replace(" ", "_")


class Triaje(BaseModel):
    """Clasificación de una incidencia propuesta por la IA."""

    categoria: str
    prioridad: Prioridad
    area_responsable: str
    justificacion: str

    @field_validator("categoria")
    @classmethod
    def _validar_categoria(cls, valor: str) -> str:
        valor = _normalizar(valor)
        if valor not in CATEGORIAS:
            raise ValueError(f"categoría '{valor}' fuera de la lista permitida")
        return valor

    @field_validator("area_responsable")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        valor = _normalizar(valor)
        if valor not in AREAS_RESPONSABLES:
            raise ValueError(f"área '{valor}' fuera de la lista permitida")
        return valor

    @field_validator("prioridad", mode="before")
    @classmethod
    def _normalizar_prioridad(cls, valor: object) -> object:
        return _normalizar(valor) if isinstance(valor, str) else valor

    @field_validator("justificacion")
    @classmethod
    def _validar_justificacion(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("la justificación está vacía")
        return valor

    @model_validator(mode="after")
    def _validar_enrutamiento(self) -> "Triaje":
        esperada = AREA_POR_CATEGORIA[self.categoria]
        if self.area_responsable != esperada:
            raise ValueError(
                f"el área '{self.area_responsable}' no corresponde a la categoría '{self.categoria}'"
            )
        return self


def clasificar_incidencia(texto: str) -> Triaje:
    """Envía el reporte a la IA y devuelve el triaje validado. Lanza IAError si la IA falla."""
    texto = texto.strip()
    if not texto:
        raise NexoCampusError("Describe la incidencia antes de clasificarla.")
    if len(texto) > MAX_CARACTERES_INCIDENCIA:
        raise NexoCampusError(
            f"La descripción es demasiado larga (máximo {MAX_CARACTERES_INCIDENCIA} caracteres)."
        )
    return consultar_json(f"Reporte de incidencia:\n{texto}", INSTRUCCIONES, Triaje)
