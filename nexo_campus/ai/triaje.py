"""Triaje de incidencias con IA: categoría, prioridad, área responsable y justificación.

La respuesta de la IA se valida contra las listas fijas de este archivo. Si la IA inventa
una categoría o un área fuera de la lista, se trata como IAError (nunca se acepta en silencio).
"""

import unicodedata

from pydantic import BaseModel, field_validator, model_validator

from nexo_campus.ai.cliente import consultar_json
from nexo_campus.errors import NexoCampusError
from nexo_campus.models import Espacio, Prioridad, Recurso, Reserva

CATEGORIAS = ["infraestructura", "tecnologia", "aseo", "seguridad", "bienestar", "otro"]
AREAS = ["mantenimiento", "soporte_ti", "servicios_generales", "seguridad", "bienestar"]
# Área a la que se enruta cada categoría. "otro" no está: la IA puede elegir cualquier área.
AREA_POR_CATEGORIA = {
    "infraestructura": "mantenimiento",
    "tecnologia": "soporte_ti",
    "aseo": "servicios_generales",
    "seguridad": "seguridad",
    "bienestar": "bienestar",
}
MAX_CARACTERES_INCIDENCIA = 1000

INSTRUCCIONES = f"""Eres el sistema de triaje de incidencias de Campuslands, un campus educativo.
Lees el reporte de una persona y lo clasificas. Puede venir con el CONTEXTO del espacio o el equipo afectado.
Responde SOLO con un objeto JSON con estas claves, en este orden:

1. "justificacion": una o dos frases en español que digan cuál es el problema real y qué tan urgente es.
   Si el contexto influyó en la prioridad, dilo. No copies el reporte.
2. "categoria": una de {CATEGORIAS}
    seguridad = algo o alguien pone en riesgo a las personas o sus cosas: robos, hurtos, extraños sospechosos,
                peleas, agresiones, humo, fuego, chispas, olor a quemado, olor a gas, cables pelados.
    bienestar = la salud o el estado emocional de una persona: desmayo, herida, dolor, crisis, estrés,
                ansiedad, acoso, burlas, discriminación, conflictos de convivencia.
    tecnologia = fallas de computadores, portátiles, proyectores, red, wifi, software, plataformas o cuentas.
    infraestructura = daños del edificio o sus instalaciones: energía eléctrica, apagones, luces, aire
                acondicionado, puertas, ventanas, sillas, mesas, tableros, goteras, tuberías, baños dañados;
                también faltantes de dotación del aula (marcadores, borradores, extensiones).
    aseo = SOLO suciedad o limpieza: basura, derrames, malos olores, falta de papel o jabón.
    otro = el texto no describe un problema del campus (saludos, opiniones, quejas de precios, texto sin sentido).
  Clasifica por el PROBLEMA, no por el objeto ni por el lugar: si roban un portátil es seguridad (no tecnologia);
  si un cable hace chispas es seguridad (no tecnologia); si alguien se desmaya es bienestar (no seguridad).
3. "prioridad": una de {[p.value for p in Prioridad]}
    critica = hay riesgo AHORA para la vida o la salud de personas (humo, fuego, chispas, gas, peleas a golpes,
              persona herida o desmayada), o la falla BLOQUEA UNA CLASE EN CURSO (el contexto dice que hay clase ahora).
    alta = algo NO FUNCIONA EN ABSOLUTO y eso impide usar un espacio o equipo, o afecta a un grupo completo
           o a todo un piso; también un robo, un extraño sospechoso, acoso, o una persona que pide ayuda emocional.
    media = algo funciona MAL pero se puede seguir trabajando (aire acondicionado débil, computador lento, gotera,
            basura acumulada).
    baja = solicitud menor o estética, sin urgencia: falta papel o jabón, faltan marcadores u otros insumos,
           un derrame pequeño, una silla floja. También todo lo que sea categoría otro.
  El contexto puede subir la prioridad: un proyector o un aula que se usan para dar clase son más urgentes
  que un equipo guardado o un espacio vacío.
4. "area_responsable": una de {AREAS}. Se deduce de la categoría, siempre así:
    {", ".join(f"{c} -> {a}" for c, a in AREA_POR_CATEGORIA.items())}.
    Para otro, elige el área más cercana o servicios_generales.

Ejemplos:
Reporte: "La puerta del aula 305 no cierra"
{{"justificacion": "La puerta es parte de las instalaciones del aula; el aula se puede usar, pero no se puede asegurar.", "categoria": "infraestructura", "prioridad": "media", "area_responsable": "mantenimiento"}}
Reporte: "Alguien abrió mi casillero y se llevó mi celular"
{{"justificacion": "Es un hurto dentro del campus y requiere atención pronta de seguridad.", "categoria": "seguridad", "prioridad": "alta", "area_responsable": "seguridad"}}
Reporte: "El video beam no prende"
Contexto: Equipo afectado: Video beam Epson (PRY-02), tipo proyector. Espacio afectado: Aula Turing (AU-201), tipo aula. Hay una clase en curso ahora: de 08:00 a 10:00 con 25 asistentes.
{{"justificacion": "El proyector no funciona y está bloqueando una clase que se está dictando en este momento.", "categoria": "tecnologia", "prioridad": "critica", "area_responsable": "soporte_ti"}}
Reporte: "buenas tardes, a qué hora abre la cafetería?"
{{"justificacion": "Es una pregunta general, no reporta ningún problema del campus.", "categoria": "otro", "prioridad": "baja", "area_responsable": "servicios_generales"}}

Usa exactamente los valores de las listas, en minúsculas y sin tildes. No agregues otras claves."""


def normalizar_opcion(valor: str) -> str:
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
        valor = normalizar_opcion(valor)
        if valor not in CATEGORIAS:
            raise ValueError(f"categoría '{valor}' fuera de la lista permitida")
        return valor

    @field_validator("area_responsable")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        valor = normalizar_opcion(valor)
        if valor not in AREAS:
            raise ValueError(f"área '{valor}' fuera de la lista permitida")
        return valor

    @field_validator("prioridad", mode="before")
    @classmethod
    def _normalizar_prioridad(cls, valor: object) -> object:
        return normalizar_opcion(valor) if isinstance(valor, str) else valor

    @field_validator("justificacion")
    @classmethod
    def _validar_justificacion(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("la justificación está vacía")
        return valor

    @model_validator(mode="after")
    def _validar_enrutamiento(self) -> "Triaje":
        esperada = AREA_POR_CATEGORIA.get(self.categoria)
        if esperada is not None and self.area_responsable != esperada:
            raise ValueError(
                f"el área '{self.area_responsable}' no corresponde a la categoría '{self.categoria}'"
            )
        return self


def _describir_contexto(
    espacio: Espacio | None, recurso: Recurso | None, reserva_en_curso: Reserva | None
) -> str:
    partes = []
    if recurso is not None:
        partes.append(
            f"Equipo afectado: {recurso.nombre} ({recurso.id}), tipo {recurso.tipo}, estado {recurso.estado.value}."
        )
    if espacio is not None:
        partes.append(
            f"Espacio afectado: {espacio.nombre} ({espacio.id}), tipo {espacio.tipo}, aforo {espacio.aforo}."
        )
        if reserva_en_curso is not None:
            partes.append(
                f"Hay una clase en curso ahora: de {reserva_en_curso.inicio:%H:%M} a "
                f"{reserva_en_curso.fin:%H:%M} con {reserva_en_curso.asistentes} asistentes."
            )
        else:
            partes.append("No hay clase en curso en este espacio ahora.")
    return " ".join(partes)


def clasificar_incidencia(
    texto: str,
    espacio: Espacio | None = None,
    recurso: Recurso | None = None,
    reserva_en_curso: Reserva | None = None,
) -> Triaje:
    """Envía el reporte a la IA, con el contexto del espacio o recurso, y devuelve el triaje validado.

    reserva_en_curso es la reserva activa del espacio en este momento, si la hay: sube la prioridad.
    Lanza IAError si la IA falla o responde algo fuera de las listas.
    """
    texto = texto.strip()
    if not texto:
        raise NexoCampusError("Describe la incidencia antes de clasificarla.")
    if len(texto) > MAX_CARACTERES_INCIDENCIA:
        raise NexoCampusError(
            f"La descripción es demasiado larga (máximo {MAX_CARACTERES_INCIDENCIA} caracteres)."
        )
    mensaje = f"Reporte: {texto}"
    contexto = _describir_contexto(espacio, recurso, reserva_en_curso)
    if contexto:
        mensaje += f"\nContexto: {contexto}"
    return consultar_json(mensaje, INSTRUCCIONES, Triaje)
