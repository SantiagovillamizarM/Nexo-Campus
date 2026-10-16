"""Convierte los valores de texto de los archivos al tipo correcto, o explica por qué no se puede."""

import unicodedata
from datetime import date, datetime, time
from enum import Enum
from typing import TypeVar

OpcionEnum = TypeVar("OpcionEnum", bound=Enum)

VALORES_VACIOS = {"", "nan", "nat", "null", "none", "n/a", "na", "-"}

FORMATOS_FECHA_HORA = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M",
)
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
FORMATOS_HORA = ("%H:%M", "%H:%M:%S", "%I:%M %p")


class DatoInvalido(ValueError):
    """Un valor de una fila no cumple el formato o la regla esperada. El mensaje es el motivo."""


def normalizar_clave(valor: object) -> str:
    """'  En Mantenimiento ' -> 'en_mantenimiento'; 'Dañado' -> 'danado'."""
    sin_tildes = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return "_".join(sin_tildes.strip().lower().replace("-", " ").split())


def es_vacio(valor: object) -> bool:
    return valor is None or str(valor).strip().lower() in VALORES_VACIOS


def texto(valor: object, campo: str, obligatorio: bool = True) -> str | None:
    if es_vacio(valor):
        if obligatorio:
            raise DatoInvalido(f"Falta el valor de '{campo}'")
        return None
    return " ".join(str(valor).split())


def codigo(valor: object, campo: str, obligatorio: bool = True) -> str | None:
    """Códigos e IDs: sin espacios a los lados y en mayúsculas, para que 'au-101' y 'AU-101' coincidan."""
    limpio = texto(valor, campo, obligatorio)
    return limpio.upper() if limpio else None


def clave(
    valor: object, campo: str, por_defecto: str | None = None, avisos: list[str] | None = None
) -> str | None:
    """Texto categórico libre (ej. tipo de espacio) normalizado como clave."""
    if es_vacio(valor):
        if por_defecto is not None and avisos is not None:
            avisos.append(f"'{campo}' vacío; se asignó '{por_defecto}'")
        return por_defecto
    return normalizar_clave(valor)


def entero(valor: object, campo: str, minimo: int | None = None, obligatorio: bool = True) -> int | None:
    if es_vacio(valor):
        if obligatorio:
            raise DatoInvalido(f"Falta el valor de '{campo}'")
        return None
    try:
        numero = float(str(valor).strip().replace(",", "."))
    except ValueError as exc:
        raise DatoInvalido(f"'{campo}' debe ser un número entero, se recibió '{valor}'") from exc
    if not numero.is_integer():
        raise DatoInvalido(f"'{campo}' debe ser un número entero, se recibió '{valor}'")
    if minimo is not None and numero < minimo:
        raise DatoInvalido(f"'{campo}' debe ser mayor o igual a {minimo}, se recibió '{valor}'")
    return int(numero)


def _intentar(valor: str, formatos: tuple[str, ...]) -> datetime | None:
    for formato in formatos:
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None


def fecha_hora(
    valor: object, campo: str, obligatorio: bool = True, fecha_base: datetime | None = None
) -> datetime | None:
    """Acepta fecha y hora, solo fecha (a las 00:00) o solo hora si se indica fecha_base."""
    if es_vacio(valor):
        if obligatorio:
            raise DatoInvalido(f"Falta el valor de '{campo}'")
        return None
    if isinstance(valor, datetime):
        return valor
    limpio = str(valor).strip()

    completa = _intentar(limpio, FORMATOS_FECHA_HORA) or _intentar(limpio, FORMATOS_FECHA)
    if completa:
        return completa

    solo_hora = _intentar(limpio.upper(), FORMATOS_HORA)
    if solo_hora:
        if fecha_base is None:
            raise DatoInvalido(f"'{campo}' solo trae la hora ('{valor}') y no hay una columna de fecha")
        return datetime.combine(date(fecha_base.year, fecha_base.month, fecha_base.day), time(solo_hora.hour, solo_hora.minute))

    raise DatoInvalido(f"Fecha inválida en '{campo}': '{valor}'")


def opcion(
    valor: object,
    campo: str,
    tipo: type[OpcionEnum],
    alias: dict[str, str] | None = None,
    obligatorio: bool = True,
    por_defecto: OpcionEnum | None = None,
    avisos: list[str] | None = None,
) -> OpcionEnum | None:
    """Convierte un texto a un valor del Enum, aceptando alias ('En mantenimiento' -> mantenimiento)."""
    if es_vacio(valor):
        if por_defecto is not None:
            if avisos is not None:
                avisos.append(f"'{campo}' vacío; se asignó '{por_defecto.value}'")
            return por_defecto
        if obligatorio:
            raise DatoInvalido(f"Falta el valor de '{campo}'")
        return None
    normalizado = normalizar_clave(valor)
    normalizado = (alias or {}).get(normalizado, normalizado)
    try:
        return tipo(normalizado)
    except ValueError as exc:
        validos = ", ".join(opcion.value for opcion in tipo)
        raise DatoInvalido(f"Valor no reconocido en '{campo}': '{valor}' (válidos: {validos})") from exc
