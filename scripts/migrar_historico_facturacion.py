"""
Migra el histórico de la planilla de facturación a Comprobantes históricos
(plan de la E2, sección 3.1, "Migración del histórico").

Es una capa fina sobre app/modulos/facturacion/services/historico.py, donde
vive toda la lógica: lee la planilla exportada en CSV, resuelve Clientes y
tareas contra el sistema de campo (con los dados de baja), clasifica, aplica,
concilia por Cliente y mes y, sólo con --aplicar, confirma. Sin --aplicar
simula: hace lo mismo y deshace al final, así los conteos y la conciliación
son los que quedarían.

Necesita la planilla en docs/modulos/facturacion/fuentes/, que está fuera de
git (ver fuentes/LEEME.md).

    python scripts/migrar_historico_facturacion.py
    python scripts/migrar_historico_facturacion.py --informe docs/modulos/facturacion/fuentes/informe.csv
    python scripts/migrar_historico_facturacion.py --aplicar
    python scripts/migrar_historico_facturacion.py --aplicar --confirmar-base <base>

**La guarda se aparta a propósito de la del script de tarifas**, que sólo
escribe en `testing`: el histórico tiene que quedar en producción. --aplicar se
permite en `testing`, o en producción si el .env tiene
PERMITIR_BASE_PRODUCCION=1 (sólo el del VPS) y, además, --confirmar-base con el
nombre exacto de la base, la convención del script de la E1. Cualquier otra
base se rechaza. Sin --aplicar, --confirmar-base no cambia nada.

**La salida tiene nombres de clientes**: nunca se pega en PRs, en la bitácora
ni en estado.md. El informe va dentro de fuentes/, que está fuera de git.

Sale con 0 sólo si no queda nada nuevo, nada cambiado y todas las diferencias
son 0: la corrida que aplica sale con 1 por los nuevos, y la simulación
siguiente es la que tiene que dar 0.
"""
import argparse
import csv
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.core.config import BASE_PRODUCCION, settings  # noqa: E402
from app.core.database import SessionExterna, SessionPropia  # noqa: E402
from app.modulos.facturacion.services.consulta_externa import (  # noqa: E402
    ConsultaExternaService,
)
from app.modulos.facturacion.services.historico import (  # noqa: E402
    Maestros, PlanillaInvalida, aplicar, clasificar, codigo_de_salida, conciliar,
    leer_planilla,
)

PLANILLA = RAIZ / "docs" / "modulos" / "facturacion" / "fuentes" / "planilla-facturacion.csv"
DESDE = date(2025, 4, 1)
BASE_DE_PRUEBA = "testing"


# ─── La guarda ──────────────────────────────────────────────────────────────

def puede_aplicar(base: str, permitir: bool) -> bool:
    """--aplicar sólo en `testing`, o en producción con el permiso del .env
    del VPS (`permitir_base_produccion`). Cualquier otra base, no."""
    nombre = base.strip().lower()
    if nombre == BASE_DE_PRUEBA:
        return True
    return nombre == BASE_PRODUCCION and permitir


# ─── Lo que lee de afuera ───────────────────────────────────────────────────

def maestros_del_campo() -> Maestros:
    """Clientes y tareas con los dados de baja, porque el histórico los
    muestra, y las fincas, del sistema de campo. Sólo lee esa base: la de
    sueldos no hace falta."""
    externa = SessionExterna()
    try:
        consulta = ConsultaExternaService(externa)
        return Maestros(
            clientes=consulta.clientes(incluir_baja=True),
            tareas=consulta.obtener_tareas(incluir_baja=True),
            fincas=consulta.todas_las_fincas(),
        )
    finally:
        externa.close()


# ─── La salida ──────────────────────────────────────────────────────────────

def _pesos(valor: Decimal) -> str:
    """Con coma decimal y dos decimales, como lo abre el Excel de la oficina."""
    return f"{valor:.2f}".replace(".", ",")


def _imprimir_resumen(clasificacion, resultado, conciliacion) -> None:
    grupos = clasificacion.grupos
    sin_numero = [g for g in grupos if g.numero is None]
    print("Comprobantes a migrar: %d (%d sin número, %d de ellos pendientes de facturar)"
          % (len(grupos), len(sin_numero),
             sum(1 for g in sin_numero if g.pendiente_de_facturar)))

    print("\nOmitidos por motivo (Comprobantes, filas):")
    por_motivo: dict[str, list[int]] = {}
    for omitido in clasificacion.omitidos:
        conteo = por_motivo.setdefault(omitido.motivo, [0, 0])
        conteo[0] += 1
        conteo[1] += len(omitido.filas)
    if not por_motivo:
        print("  ninguno")
    for motivo in sorted(por_motivo):
        print("  %s: %d, %d filas" % (motivo, *por_motivo[motivo]))

    print("\nAvisos por motivo:")
    avisos: dict[str, int] = {}
    for aviso in clasificacion.avisos:
        avisos[aviso.motivo] = avisos.get(aviso.motivo, 0) + 1
    if not avisos:
        print("  ninguno")
    for motivo in sorted(avisos):
        print("  %s: %d" % (motivo, avisos[motivo]))

    print("\nNombres no resueltos (filas):")
    if not clasificacion.no_resueltos:
        print("  ninguno")
    for (motivo, nombre), filas in sorted(clasificacion.no_resueltos.items()):
        print("  %s  %s: %d" % (motivo, nombre, filas))

    print("\nAplicar:")
    for nombre, cantidad in resultado.conteos().items():
        print("  %s: %d" % (nombre, cantidad))

    diferencias = conciliacion.con_diferencia()
    if not diferencias:
        print("\nDiferencias: 0")
        return
    print("\nCeldas con diferencia (cliente, mes: migrable, en base, diferencia):")
    for (cliente, mes), celda in diferencias:
        print("  %s, %s: %s, %s, %s" % (cliente, mes, _pesos(celda.migrable),
                                        _pesos(celda.en_base), _pesos(celda.diferencia)))


def escribir_informe(ruta: Path, conciliacion) -> None:
    """La tabla completa de la conciliación, una fila por (Cliente, mes),
    también las que cierran. El omitido va en total y abierto por motivo: una
    columna por cada motivo que aparece, en 0 donde no lo hay. CSV con `;` y
    coma decimal, en UTF-8 con BOM, para que Excel lo abra bien."""
    motivos = sorted({m for c in conciliacion.celdas.values() for m in c.omitido})
    with Path(ruta).open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow(
            ["cliente", "mes", "planilla", "sin_numero", "pendiente", "omitido"]
            + [f"omitido_{m}" for m in motivos]
            + ["migrable", "en_base", "diferencia"]
        )
        for (cliente, mes), celda in sorted(conciliacion.celdas.items()):
            escritor.writerow(
                [cliente, mes, _pesos(celda.planilla), _pesos(celda.sin_numero),
                 _pesos(celda.pendiente),
                 _pesos(sum(celda.omitido.values(), Decimal("0")))]
                + [_pesos(celda.omitido.get(m, Decimal("0"))) for m in motivos]
                + [_pesos(celda.migrable), _pesos(celda.en_base), _pesos(celda.diferencia)]
            )


# ─── Main ───────────────────────────────────────────────────────────────────

def _argumentos(argv):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planilla", nargs="?", type=Path, default=PLANILLA,
                    help="el CSV exportado (por defecto, el de fuentes/ de este checkout)")
    ap.add_argument("--aplicar", action="store_true", help="escribir de verdad")
    ap.add_argument("--confirmar-base", metavar="NOMBRE",
                    help="nombre de la base propia, obligatorio para escribir "
                         "en una que no sea 'testing'")
    ap.add_argument("--reemplazar-cambiados", action="store_true",
                    help="reemplazar las Líneas y la fecha de los históricos que cambiaron")
    ap.add_argument("--desde", type=date.fromisoformat, default=DESDE,
                    help="fecha de inicio, AAAA-MM-DD (por defecto, %s)" % DESDE.isoformat())
    ap.add_argument("--informe", type=Path,
                    help="dónde escribir la conciliación completa en CSV (mejor, dentro de fuentes/)")
    return ap.parse_args(argv)


def main(argv=None, *, abrir_sesion=None, leer_maestros=None, base=None,
         permitir=None) -> int:
    """Todo lo que toca afuera se puede inyectar, para probarlo sin bases:
    la sesión propia, los maestros del campo, y la base y el permiso del
    .env."""
    args = _argumentos(argv)
    abrir_sesion = abrir_sesion or SessionPropia
    leer_maestros = leer_maestros or maestros_del_campo
    base = settings.db_propia_name if base is None else base
    permitir = settings.permitir_base_produccion if permitir is None else permitir

    if not args.planilla.exists():
        print("No encuentro %s. La planilla va en docs/modulos/facturacion/fuentes/, "
              "que está fuera de git: ver fuentes/LEEME.md." % args.planilla)
        return 1
    try:
        filas = leer_planilla(args.planilla)
    except PlanillaInvalida as error:
        print(error)
        return 1

    if args.aplicar:
        if not puede_aplicar(base, permitir):
            print("La base propia es %r. --aplicar sólo escribe en 'testing', o en '%s' "
                  "con PERMITIR_BASE_PRODUCCION=1. No se escribió nada."
                  % (base, BASE_PRODUCCION))
            return 1
        nombre = base.strip()
        if nombre.lower() != BASE_DE_PRUEBA and args.confirmar_base != nombre:
            print("La base propia es %r. Para escribir en una base que no es %r, "
                  "pasá --confirmar-base %s. No se escribió nada."
                  % (base, BASE_DE_PRUEBA, nombre))
            return 1

    print("Base propia: %s. %s" % (base, "APLICANDO" if args.aplicar
                                   else "Simulación: no se escribe nada."))
    print("Planilla: %s, %d filas, desde %s.\n" % (args.planilla, len(filas),
                                                   args.desde.isoformat()))

    maestros = leer_maestros()
    clasificacion = clasificar(filas, maestros, args.desde)

    db = abrir_sesion()
    try:
        resultado = aplicar(db, clasificacion, reemplazar_cambiados=args.reemplazar_cambiados)
        conciliacion = conciliar(db, clasificacion, resultado, args.desde)
        _imprimir_resumen(clasificacion, resultado, conciliacion)
        if args.informe:
            escribir_informe(args.informe, conciliacion)
            print("\nInforme: %s" % args.informe)
        if args.aplicar:
            db.commit()
            print("\nConfirmado en la base %s." % base)
        else:
            db.rollback()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

    salida = codigo_de_salida(resultado, conciliacion)
    print("Salida: %d" % salida)
    return salida


if __name__ == "__main__":
    sys.exit(main())
