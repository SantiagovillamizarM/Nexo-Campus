from datetime import datetime

from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoIncidencia, OrigenClasificacion, Prioridad


class Incidencia(SQLModel, table=True):
    """Incidencia o solicitud reportada sobre un espacio, un recurso o el campus en general."""

    id: int | None = Field(default=None, primary_key=True)
    codigo_origen: str | None = Field(default=None, index=True)  # ID en los datos oficiales, si venía
    descripcion: str  # texto original del reporte
    reportante: str | None = None
    espacio_id: str | None = Field(default=None, foreign_key="espacio.id", index=True)
    recurso_id: str | None = Field(default=None, foreign_key="recurso.id", index=True)
    fecha_reporte: datetime | None = None

    # Clasificación (la llena la IA, una persona o venía en los datos oficiales)
    categoria: str | None = None
    prioridad: Prioridad | None = Field(default=None, index=True)
    area_responsable: str | None = None
    justificacion: str | None = None
    origen_clasificacion: OrigenClasificacion | None = None

    estado: EstadoIncidencia = Field(default=EstadoIncidencia.abierta, index=True)
    fecha_cierre: datetime | None = None
