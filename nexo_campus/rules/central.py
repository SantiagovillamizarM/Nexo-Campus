"""Regla central unificada: qué incidencias bloquean un espacio o un equipo.

Una incidencia abierta con una de estas prioridades inhabilita el espacio o equipo afectado,
así que no se puede reservar ni prestar. Al cerrarse, vuelve al estado que tenía.
"""

from nexo_campus.models import Prioridad

PRIORIDADES_QUE_BLOQUEAN = {Prioridad.alta, Prioridad.critica}


def bloquea(prioridad: Prioridad | None) -> bool:
    return prioridad in PRIORIDADES_QUE_BLOQUEAN
