"""Carga los datos oficiales de data/raw/ a SQLite e imprime el reporte de calidad.

Uso (desde la raíz del proyecto):
    python scripts/cargar_datos.py              # primera carga
    python scripts/cargar_datos.py --reiniciar  # borra la base y vuelve a cargar desde cero
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nexo_campus import config  # noqa: E402
from nexo_campus.carga import cargar_datos  # noqa: E402
from nexo_campus.errors import NexoCampusError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga los datos oficiales de Campuslands en SQLite.")
    parser.add_argument("--reiniciar", action="store_true", help="borra la base de datos y carga desde cero")
    parser.add_argument("--directorio", type=Path, default=config.DATA_DIR, help="carpeta con los archivos de datos")
    args = parser.parse_args()

    try:
        reporte = cargar_datos(directorio=args.directorio, reiniciar=args.reiniciar)
    except NexoCampusError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Base de datos: {config.DATABASE_PATH}\n")
    print(f"{'Entidad':<12} {'Archivo':<20} {'Leídos':>7} {'Cargados':>9} {'Rechazados':>11} {'Advertencias':>13}")
    for r in reporte.resumen:
        print(
            f"{r.entidad:<12} {(r.archivo or '-'):<20} {r.leidos:>7} {r.cargados:>9} {r.rechazados:>11} {r.advertencias:>13}"
        )

    if reporte.inconsistencias:
        print("\nInconsistencias encontradas:")
        for i in reporte.inconsistencias:
            ubicacion = f"fila {i.fila}" if i.fila else "archivo"
            identificador = f" [{i.identificador}]" if i.identificador else ""
            print(f"  - {i.tipo.value.upper():<11} {i.entidad} ({ubicacion}){identificador}: {i.motivo}")

    print(f"\nTotal: {reporte.total_cargados} registros cargados, {reporte.total_rechazados} rechazados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
