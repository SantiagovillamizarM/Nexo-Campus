from datetime import datetime

from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoPrestamo


class Prestamo(SQLModel, table=True):
    """Préstamo de un recurso a una persona."""

    id: int | None = Field(default=None, primary_key=True)
    codigo_origen: str | None = Field(default=None, index=True)  # ID en los datos oficiales, si venía
    recurso_id: str = Field(foreign_key="recurso.id", index=True)
    solicitante: str = Field(index=True)
    fecha_prestamo: datetime
    fecha_devolucion_prevista: datetime | None = None
    fecha_devolucion: datetime | None = None  # se llena al devolver
    estado: EstadoPrestamo = Field(default=EstadoPrestamo.activo, index=True)
