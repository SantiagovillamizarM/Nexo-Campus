from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoEspacio


class Espacio(SQLModel, table=True):
    """Aula, cubículo u otro espacio reservable del campus."""

    # Streamlit vuelve a importar los módulos al detectar cambios; sin esto falla con
    # "Table ... is already defined for this MetaData instance".
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True)  # código de los datos oficiales (ej. AU-101)
    nombre: str
    tipo: str = Field(index=True)  # aula, cubiculo, laboratorio...
    aforo: int
    ubicacion: str | None = None
    estado: EstadoEspacio = Field(default=EstadoEspacio.disponible, index=True)
