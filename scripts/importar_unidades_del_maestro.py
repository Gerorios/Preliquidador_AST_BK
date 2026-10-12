"""
Primera carga de la Unidad sugerida y la marca No facturable de cada tarea del
campo, a partir del maestro de tareas de la planilla de facturación.

El maestro es un CSV con el encabezado `nombre_tarea;grupo_tarea;grupo_factura`
(UTF-8, separado por `;`). Vive en docs/modulos/facturacion/fuentes/, que está
fuera de git: tiene nombres reales de tareas. Viene por nombre y se cruza
contra las tareas activas del campo para guardarlo por id.

**Sólo completa lo vacío.** Una tarea que ya tiene algo definido no se toca; si
el CSV dice otra cosa, se lista. Lo que no cruza, lo ambiguo y lo repetido con
grupos distintos tampoco se carga: queda Sin definir y se completa a mano en la
pantalla Unidad de medida por defecto.

    python scripts/importar_unidades_del_maestro.py --csv <ruta>
    python scripts/importar_unidades_del_maestro.py --csv <ruta> --aplicar
    python scripts/importar_unidades_del_maestro.py --csv <ruta> --aplicar --confirmar-base <base>

Sin --aplicar sólo muestra qué haría. Con --aplicar sobre una base que no sea
`testing` hace falta además --confirmar-base con el nombre de esa base.
Lo que carga queda sin persona (actualizado_por en NULL): para deshacerlo,
DELETE FROM facturacion_tarea WHERE actualizado_por IS NULL.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import guardia_base_propia, settings  # noqa: E402
from app.core.database import (  # noqa: E402
    ExternaNoDisponible, SessionExterna, SessionPropia,
)
from app.modulos.facturacion.services.consulta_externa import (  # noqa: E402
    ConsultaExternaService,
)
from app.modulos.facturacion.services.primera_carga import (  # noqa: E402
    MaestroInvalido, aplicar, definidas, leer_maestro, planificar,
)
from app.modulos.facturacion.unidades import ETIQUETAS  # noqa: E402

BASE_DE_PRUEBA = "testing"
FUENTES = "docs/modulos/facturacion/fuentes/"


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="ruta del maestro de tareas (CSV)")
    ap.add_argument("--aplicar", action="store_true", help="escribir de verdad")
    ap.add_argument("--confirmar-base", metavar="NOMBRE",
                    help="nombre de la base propia, obligatorio para escribir "
                         "en una que no sea 'testing'")
    return ap


def tareas_del_campo() -> list[dict]:
    """Las tareas activas del sistema de campo. Aparte, para que los tests la
    reemplacen sin conectar."""
    db = SessionExterna()
    try:
        return ConsultaExternaService(db).obtener_tareas()
    finally:
        db.close()


def _valor(valor) -> str:
    unidad, no_facturable = valor
    if no_facturable:
        return "No facturable"
    return ETIQUETAS.get(unidad, unidad) if unidad else "Sin definir"


def _seccion(titulo: str, lineas: list[str]) -> None:
    print("\n%s: %d" % (titulo, len(lineas)))
    for linea in lineas:
        print("   " + linea)


def imprimir_informe(plan) -> None:
    print("A cargar: %d (%d con Unidad sugerida, %d No facturables)"
          % (len(plan.a_cargar), plan.unidades_a_cargar, plan.no_facturables_a_cargar))
    for c in plan.a_cargar:
        print("   %-50s %s" % (c["nombre"][:50], _valor((c["unidad_sugerida"], c["no_facturable"]))))
    _seccion("Sin grupo en el CSV", plan.sin_grupo)
    _seccion("Grupo desconocido", ["%s -> %s" % (n, g) for n, g in plan.grupo_desconocido])
    _seccion("No está entre las activas del campo", plan.no_activa)
    _seccion("Nombre ambiguo en el campo (ids)",
             ["%s -> %s" % (n, ", ".join(str(i) for i in ids)) for n, ids in plan.ambigua_en_campo])
    _seccion("Repetida en el CSV con grupos distintos (no se carga ninguna)",
             ["%s -> %s" % (n, " / ".join(g or "(vacío)" for g in gs)) for n, gs in plan.repetida_en_csv])
    print("\nYa definidas, no se tocan: %d" % len(plan.ya_definidas))
    _seccion("   De ellas, el CSV dice otra cosa",
             ["%s: tiene %s, el CSV dice %s" % (d["nombre"], _valor(d["actual"]), _valor(d["csv"]))
              for d in plan.contradichas])
    _seccion("Tareas activas del campo que no están en el CSV",
             ["%s (id %s)" % (t["nombre"], t["tarea_id"]) for t in plan.faltan_en_csv])


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    base = settings.db_propia_name.strip()

    # Antes de conectar a nada: la misma guardia que el arranque de la app.
    motivo = guardia_base_propia(base, settings.permitir_base_produccion)
    if motivo:
        print("No sigo: %s" % motivo)
        return 1
    if args.aplicar and base != BASE_DE_PRUEBA and args.confirmar_base != base:
        print("La base propia es %r. Para escribir en una base que no es %r, "
              "pasá --confirmar-base %s." % (base, BASE_DE_PRUEBA, base))
        return 1

    ruta = Path(args.csv)
    if not ruta.is_file():
        print("No encuentro %s. El maestro vive en %s, que está fuera de git." % (ruta, FUENTES))
        return 1
    try:
        filas = leer_maestro(ruta)
    except MaestroInvalido as e:
        print(str(e))
        return 1

    try:
        tareas = tareas_del_campo()
    except ExternaNoDisponible as e:
        print(str(e))
        return 1

    db = SessionPropia()
    try:
        plan = planificar(filas, tareas, definidas(db))
        print("Base propia: %s — %s" % (base, "APLICANDO" if args.aplicar else "simulación, no escribe"))
        print("CSV: %d filas. Campo: %d tareas activas.\n" % (len(filas), len(tareas)))
        imprimir_informe(plan)
        if args.aplicar:
            print("\nCargadas: %d." % aplicar(db, plan))
        else:
            print("\nSe cargarían %d. Para escribir, --aplicar." % len(plan.a_cargar))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
