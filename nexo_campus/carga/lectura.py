"""Encuentra y lee los archivos de datos (CSV, Excel o JSON) como filas de texto."""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from nexo_campus.carga.normalizacion import normalizar_clave
from nexo_campus.errors import DatosInconsistentesError

EXTENSIONES = (".csv", ".xlsx", ".xls", ".json")


@dataclass
class Tabla:
    columnas: list[str]  # nombres tal como vienen en el archivo
    filas: list[dict[str, str]]  # todos los valores como texto ("" si está vacío)
    primera_fila: int  # número de la primera fila de datos, para reportar ubicaciones reales


def buscar_archivo(directorio: Path, nombre_base: str) -> Path | None:
    """Busca '<nombre_base>.<csv|xlsx|xls|json>' sin importar mayúsculas ni tildes del nombre."""
    for ruta in sorted(directorio.iterdir()):
        if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES and normalizar_clave(ruta.stem) == nombre_base:
            return ruta
    return None


def _leer_csv(ruta: Path) -> pd.DataFrame:
    # sep=None detecta si el separador es coma, punto y coma o tabulación.
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(ruta, dtype=str, keep_default_na=False, sep=None, engine="python", encoding=codificacion)
        except UnicodeDecodeError:
            continue
    raise DatosInconsistentesError(f"No se pudo leer {ruta.name}: codificación de texto no reconocida")


def _leer_json(ruta: Path) -> pd.DataFrame:
    contenido = json.loads(ruta.read_text(encoding="utf-8-sig"))
    # Acepta una lista de objetos o un objeto con una sola lista dentro ({"espacios": [...]})
    if isinstance(contenido, dict):
        listas = [valor for valor in contenido.values() if isinstance(valor, list)]
        if len(listas) != 1:
            raise DatosInconsistentesError(f"{ruta.name} debe contener una lista de registros")
        contenido = listas[0]
    if not isinstance(contenido, list):
        raise DatosInconsistentesError(f"{ruta.name} debe contener una lista de registros")
    return pd.DataFrame(contenido)


def leer_tabla(ruta: Path) -> Tabla:
    try:
        extension = ruta.suffix.lower()
        if extension == ".csv":
            datos, primera_fila = _leer_csv(ruta), 2  # la fila 1 es el encabezado
        elif extension in (".xlsx", ".xls"):
            datos, primera_fila = pd.read_excel(ruta, dtype=str, keep_default_na=False), 2
        else:
            datos, primera_fila = _leer_json(ruta), 1
    except DatosInconsistentesError:
        raise
    except Exception as exc:  # archivo vacío, corrupto o con formato inesperado
        raise DatosInconsistentesError(f"No se pudo leer {ruta.name}: {exc}") from exc

    datos = datos.astype(object).where(datos.notna(), "")
    columnas = [str(columna) for columna in datos.columns]
    filas = [{columna: str(valor) for columna, valor in zip(columnas, fila)} for fila in datos.itertuples(index=False)]
    return Tabla(columnas=columnas, filas=filas, primera_fila=primera_fila)


def mapear_columnas(tabla: Tabla, alias_por_campo: dict[str, list[str]]) -> tuple[list[dict[str, str]], list[str]]:
    """Renombra las columnas del archivo a los campos del modelo.

    Devuelve las filas con solo los campos reconocidos y la lista de campos sin columna.
    """
    columna_de_campo: dict[str, str] = {}
    usadas: set[str] = set()

    def asignar(campo: str, nombre: str) -> bool:
        for columna in tabla.columnas:
            if columna not in usadas and normalizar_clave(columna) == normalizar_clave(nombre):
                columna_de_campo[campo] = columna
                usadas.add(columna)
                return True
        return False

    # Primero el nombre exacto del campo, luego los alias en orden de preferencia, para que un
    # alias genérico de un campo (ej. "fecha") no le quite la columna a otro que se llama así.
    for campo in alias_por_campo:
        asignar(campo, campo)
    for campo, alias in alias_por_campo.items():
        if campo not in columna_de_campo:
            any(asignar(campo, nombre) for nombre in alias)

    filas = [{campo: fila[columna] for campo, columna in columna_de_campo.items()} for fila in tabla.filas]
    faltantes = [campo for campo in alias_por_campo if campo not in columna_de_campo]
    return filas, faltantes
