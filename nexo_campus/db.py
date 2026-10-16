"""Conexión a SQLite. Los repositorios abren sesiones con obtener_sesion()."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from nexo_campus import config
from nexo_campus import models  # noqa: F401  (registra las tablas en SQLModel.metadata)


def crear_motor(url: str = config.DATABASE_URL) -> Engine:
    if url == config.DATABASE_URL:
        config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    motor = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite no valida claves foráneas si no se activa en cada conexión.
    @event.listens_for(motor, "connect")
    def _activar_claves_foraneas(conexion, _registro) -> None:
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return motor


motor = crear_motor()


def crear_tablas(motor_db: Engine = motor) -> None:
    """Crea las tablas que no existan. No borra datos."""
    SQLModel.metadata.create_all(motor_db)


def reiniciar_tablas(motor_db: Engine = motor) -> None:
    """Borra todas las tablas y las vuelve a crear vacías."""
    SQLModel.metadata.drop_all(motor_db)
    SQLModel.metadata.create_all(motor_db)


@contextmanager
def obtener_sesion(motor_db: Engine = motor) -> Iterator[Session]:
    with Session(motor_db, expire_on_commit=False) as sesion:
        yield sesion
