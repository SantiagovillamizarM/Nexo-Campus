from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoEspacio


class Espacio(SQLModel, table=True):
    """Aula, cubículo u otro espacio reservable del campus."""

    id: str = Field(primary_key=True)  # código de los datos oficiales (ej. AU-101)
    nombre: str
    tipo: str = Field(index=True)  # aula, cubiculo, laboratorio...
    aforo: int
    ubicacion: str | None = None
    estado: EstadoEspacio = Field(default=EstadoEspacio.disponible, index=True)
