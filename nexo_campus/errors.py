"""Excepciones propias de Nexo Campus.

La UI captura estas excepciones y muestra su mensaje al usuario con st.error.
"""


class NexoCampusError(Exception):
    """Error base del sistema. Su mensaje debe ser entendible por un usuario final."""


class ReglaNegocioError(NexoCampusError):
    """Se lanza cuando una operación incumple una regla de negocio."""


class DatosInconsistentesError(NexoCampusError):
    """Se lanza cuando un registro de los datos de origen no es válido."""


class IAError(NexoCampusError):
    """Se lanza cuando la IA falla, no responde a tiempo o devuelve una respuesta inválida."""
