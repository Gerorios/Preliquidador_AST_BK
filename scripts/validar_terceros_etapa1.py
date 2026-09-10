"""
Compara las cuatro consultas del módulo Liquidación Terceros contra las hojas
de aterrizaje del Excel que hoy resuelve el circuito. Es la comprobación con la
que se da por terminada la etapa 1 del plan (docs/modulos/terceros/plan-terceros.md):
"los números coinciden con el Excel para una quincena conocida".

No es un test: necesita las bases reales, la URL del Sheet de la app del taller
y el Excel maestro en docs/modulos/terceros/fuentes/, que está fuera de git.

    python scripts/validar_terceros_etapa1.py --quincena 2026-08-01
    python scripts/validar_terceros_etapa1.py --quincena 2026-08-01 --sin-taller

Devuelve 0 si las cuatro coinciden, 1 si alguna no.
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from app.core.database import SessionExterna, SessionSueldos  # noqa: E402
from app.modulos.terceros.services.consulta_externa import ConsultaExternaService  # noqa: E402
from app.modulos.terceros.services.consulta_taller import (  # noqa: E402
    descargar_libro,
    leer_horas,
)

EXCEL = Path("docs/modulos/terceros/fuentes/Liquidacion_Fletes_Master_67.xlsx")

# Cada consulta del módulo con la hoja del Excel que hoy alimenta, la columna
# de la que se suma el total y la columna del módulo equivalente.
COMPARACIONES = (
    ("viajes",      "Chinagro-Viajes",       "cantidadviajes",  "cantidadviajes"),
    ("combustible", "Chinagro-Combustible",  "litros_cargados", "litros_cargados"),
    ("repuestos",   "La Falda",              "Monto_Total",     "monto_total"),
    ("horas",       "App-Horas Taller",      "Horas_Total",     "horas_total"),
)


def quincena_mes(f: date) -> str:
    return f"{f.month:02d}-{1 if f.day <= 15 else 2}Q"


def _fecha_excel(valor):
    """En algunas hojas la fecha quedó como número de serie de Excel."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date(1899, 12, 30) + timedelta(days=int(valor))


def _decimal(valor) -> Decimal:
    if valor is None or valor == "":
        return Decimal(0)
    return Decimal(str(valor))


def leer_hoja(libro, hoja: str, quincena: str, columna: str):
    ws = libro[hoja]
    filas = ws.iter_rows(values_only=True)
    cabecera = next(filas)
    indice = {str(c).strip(): n for n, c in enumerate(cabecera) if c is not None}
    clave_quincena = "Quincena_mes" if "Quincena_mes" in indice else "quincena_mes"
    cantidad, total = 0, Decimal(0)
    for fila in filas:
        if not any(v is not None for v in fila):
            continue
        if fila[indice[clave_quincena]] != quincena:
            continue
        cantidad += 1
        total += _decimal(fila[indice[columna]])
    return cantidad, total


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--quincena", required=True,
                    help="fecha de inicio de la quincena, AAAA-MM-DD (1 o 16)")
    ap.add_argument("--sin-taller", action="store_true",
                    help="no bajar el Sheet de la app del taller")
    args = ap.parse_args()

    quincena = date.fromisoformat(args.quincena)
    if quincena.day not in (1, 16):
        print("La quincena empieza el 1 o el 16.")
        return 1
    if not EXCEL.exists():
        print(f"No encuentro {EXCEL}. Está fuera de git: ver fuentes/LEEME.md.")
        return 1

    etiqueta = quincena_mes(quincena)
    print(f"Quincena {etiqueta} ({quincena})\n")

    db_externa, db_sueldos = SessionExterna(), SessionSueldos()
    try:
        servicio = ConsultaExternaService(db_externa, db_sueldos)
        modulo = {
            "viajes": servicio.viajes(quincena),
            "combustible": servicio.cargas_combustible(quincena),
            "repuestos": servicio.repuestos(quincena),
        }
    finally:
        db_externa.close()
        db_sueldos.close()

    if args.sin_taller:
        modulo["horas"] = None
    else:
        modulo["horas"] = leer_horas(descargar_libro(), quincena)

    libro = openpyxl.load_workbook(EXCEL, read_only=True, data_only=True)
    print(f"{'consulta':13} {'filas módulo':>13} {'filas Excel':>12} "
          f"{'total módulo':>18} {'total Excel':>18}  ")
    todo_bien = True
    for nombre, hoja, columna_excel, columna_modulo in COMPARACIONES:
        filas = modulo[nombre]
        if filas is None:
            print(f"{nombre:13} {'(salteado)':>13}")
            continue
        total_modulo = sum((_decimal(f[columna_modulo]) for f in filas), Decimal(0))
        cantidad_excel, total_excel = leer_hoja(libro, hoja, etiqueta, columna_excel)
        coincide = len(filas) == cantidad_excel and total_modulo == total_excel
        todo_bien = todo_bien and coincide
        print(f"{nombre:13} {len(filas):>13} {cantidad_excel:>12} "
              f"{total_modulo:>18} {total_excel:>18}  {'OK' if coincide else 'NO COINCIDE'}")

    # El desvío de la corrección pendiente de fecha en repuestos: con cuántas
    # líneas cambiaría la quincena si se imputara por la fecha de descarga.
    repuestos = modulo["repuestos"]
    mueven = [f for f in repuestos
              if quincena_mes(f["fecha"]) != quincena_mes(f["fecha_descarga"])]
    if repuestos:
        plata = sum((_decimal(f["monto_total"]) for f in mueven), Decimal(0))
        print(f"\nRepuestos, fecha de descarga vs. encabezado: cambian de quincena "
              f"{len(mueven)} de {len(repuestos)} líneas (${plata}).")
        print("Es la corrección pendiente de plan-terceros.md, sección 3; se aplica")
        print("en la quincena de corte, no antes.")

    print("\nLas cuatro coinciden." if todo_bien else "\nHay diferencias: revisar arriba.")
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
