from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoRecurso


class Recurso(SQLModel, table=True):
    """Equipo tecnológico prestable (portátil, proyector, etc.)."""

    id: str = Field(primary_key=True)  # código de los datos oficiales (ej. PC-001)
    nombre: str
    tipo: str = Field(index=True)  # portatil, proyector, tablet...
    estado: EstadoRecurso = Field(default=EstadoRecurso.disponible, index=True)
    ubicacion: str | None = None
