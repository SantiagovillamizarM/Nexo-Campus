from datetime import datetime

from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoReserva


class Reserva(SQLModel, table=True):
    """Reserva de un espacio en una franja horaria."""

    id: int | None = Field(default=None, primary_key=True)
    codigo_origen: str | None = Field(default=None, index=True)  # ID en los datos oficiales, si venía
    espacio_id: str = Field(foreign_key="espacio.id", index=True)
    solicitante: str
    inicio: datetime
    fin: datetime
    asistentes: int
    motivo: str | None = None
    estado: EstadoReserva = Field(default=EstadoReserva.activa, index=True)
