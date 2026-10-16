from datetime import datetime

from sqlmodel import Field, SQLModel

from nexo_campus.models.enums import TipoInconsistencia


class RegistroInconsistente(SQLModel, table=True):
    """Problema encontrado al cargar los datos oficiales. Es la evidencia del reporte de calidad."""

    id: int | None = Field(default=None, primary_key=True)
    entidad: str = Field(index=True)  # espacios, recursos, reservas...
    archivo: str | None = None
    fila: int | None = None  # fila del archivo (None si el problema es del archivo completo)
    identificador: str | None = None  # ID del registro, si se pudo leer
    motivo: str
    tipo: TipoInconsistencia = Field(index=True)
    registrado_en: datetime = Field(default_factory=datetime.now)
