from datetime import datetime

from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import EstadoEspacio, EstadoRecurso, OrigenCambioEstado


class HistorialEstadoRecurso(SQLModel, table=True):
    """Cada cambio de estado de un recurso: de qué estado pasó a cuál, por qué y quién lo provocó."""

    # Streamlit vuelve a importar los módulos al detectar cambios; sin esto falla con
    # "Table ... is already defined for this MetaData instance".
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    recurso_id: str = Field(foreign_key="recurso.id", index=True)
    estado_anterior: EstadoRecurso
    estado_nuevo: EstadoRecurso
    motivo: str | None = None
    origen: OrigenCambioEstado = Field(index=True)
    fecha: datetime = Field(default_factory=datetime.now, index=True)


class HistorialEstadoEspacio(SQLModel, table=True):
    """Cada cambio de estado de un espacio. La regla central lo usa para saber qué estado devolver al cerrar una incidencia."""

    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    espacio_id: str = Field(foreign_key="espacio.id", index=True)
    estado_anterior: EstadoEspacio
    estado_nuevo: EstadoEspacio
    motivo: str | None = None
    origen: OrigenCambioEstado = Field(index=True)
    fecha: datetime = Field(default_factory=datetime.now, index=True)
