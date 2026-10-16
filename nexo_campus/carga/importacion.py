"""Importación de los archivos oficiales subidos desde la aplicación.

Guarda cada archivo en data/raw/ con el nombre que espera la carga (espacios.csv, recursos.xlsx...)
y ejecuta la misma carga de siempre, con su reporte de inconsistencias.
"""

from pathlib import Path

from sqlalchemy import Engine

from nexo_campus import config, db
from nexo_campus.carga.cargador import ENTIDADES, ReporteCarga, _hay_datos, cargar_datos
from nexo_campus.carga.esquema import ARCHIVOS
from nexo_campus.carga.lectura import EXTENSIONES
from nexo_campus.carga.normalizacion import normalizar_clave
from nexo_campus.errors import NexoCampusError

TAMANO_MAXIMO_MB = 20

# Palabras con las que se reconoce a qué entidad corresponde un archivo por su nombre
_PISTAS = {
    "espacios": ("espacio", "aula", "salon", "cubiculo"),
    "recursos": ("recurso", "equipo", "inventario"),
    "reservas": ("reserva",),
    "prestamos": ("prestamo",),
    "incidencias": ("incidencia", "ticket", "solicitud"),
}


def adivinar_entidad(nombre_archivo: str) -> str | None:
    """'Espacios_Campus 2026.xlsx' -> 'espacios'. None si el nombre no da pistas."""
    nombre = normalizar_clave(Path(nombre_archivo).stem)
    return next((entidad for entidad, pistas in _PISTAS.items() if any(p in nombre for p in pistas)), None)


def hay_datos_cargados(motor_db: Engine = db.motor) -> bool:
    db.crear_tablas(motor_db)
    return _hay_datos(motor_db)


def importar_archivos(
    archivos: dict[str, tuple[str, bytes]],
    reemplazar: bool,
    directorio: Path | None = None,
    motor_db: Engine = db.motor,
) -> ReporteCarga:
    """archivos: entidad -> (nombre original, contenido). Valida todo antes de escribir en disco."""
    directorio = Path(directorio or config.DATA_DIR)
    if not archivos:
        raise NexoCampusError("Selecciona al menos un archivo para cargar.")
    for entidad, (nombre, contenido) in archivos.items():
        if entidad not in ENTIDADES:
            raise NexoCampusError(f"'{entidad}' no es un tipo de datos válido.")
        if Path(nombre).suffix.lower() not in EXTENSIONES:
            raise NexoCampusError(f"{nombre}: formato no soportado (usa CSV, Excel o JSON).")
        if not contenido:
            raise NexoCampusError(f"{nombre} está vacío.")
        if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
            raise NexoCampusError(f"{nombre} supera el tamaño máximo de {TAMANO_MAXIMO_MB} MB.")
    if hay_datos_cargados(motor_db) and not reemplazar:
        raise NexoCampusError(
            "Ya hay información cargada. Confirma que quieres reemplazarla: se borrarán también las reservas, "
            "préstamos e incidencias registradas desde la aplicación."
        )

    directorio.mkdir(parents=True, exist_ok=True)
    for entidad, (nombre, contenido) in archivos.items():
        base = ARCHIVOS[entidad]
        # Un solo archivo por entidad: se quitan versiones anteriores con otra extensión.
        for anterior in directorio.iterdir():
            if anterior.is_file() and anterior.suffix.lower() in EXTENSIONES and normalizar_clave(anterior.stem) == base:
                anterior.unlink()
        (directorio / f"{base}{Path(nombre).suffix.lower()}").write_bytes(contenido)

    return cargar_datos(motor_db, directorio, reiniciar=True)
