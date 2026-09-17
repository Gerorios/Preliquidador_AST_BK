"""
Carga el tarifario de una quincena a partir de los precios que hoy están
tipeados fila por fila en el Excel maestro.

Es la puerta de entrada para probar el módulo con datos reales: el Excel tiene
unos 6.600 precios escritos a mano por año, y de ahí salen las reglas del
tarifario. No sustituye al trabajo del liquidador — sirve para arrancar con lo
ya pactado en vez de tipear todo de nuevo.

**Lo que no es consistente no se importa.** Si una misma combinación tiene dos
precios distintos en la misma quincena, el script no elige: lo lista y sigue.
Adivinar ahí sería meter en el sistema un precio que nadie decidió.

Necesita el Excel en docs/modulos/terceros/fuentes/, que está fuera de git.

    python scripts/importar_tarifas_del_excel.py --quincena 2026-08-01
    python scripts/importar_tarifas_del_excel.py --quincena 2026-08-01 --aplicar

Sin --aplicar sólo muestra qué haría.
"""
import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionPropia  # noqa: E402
from app.modulos.terceros.models import (  # noqa: E402
    HoraReparacion, Liquidacion,
)
from app.modulos.terceros.services.tarifario_service import (  # noqa: E402
    TarifaInvalida, TarifarioService,
)

EXCEL = Path("docs/modulos/terceros/fuentes/Liquidacion_Fletes_Master_68 (2).xlsx")


def etiqueta(q) -> str:
    return "%02d-%dQ" % (q.month, 1 if q.day <= 15 else 2)


def _t(v) -> str:
    return str(v).strip() if v is not None else ""


def _d(v):
    return None if v in (None, "") else Decimal(str(v))


def leer(wb, hoja):
    ws = wb[hoja]
    it = ws.iter_rows(values_only=True)
    cols = [str(c).strip() if c is not None else "" for c in next(it)]
    return [dict(zip(cols, f)) for f in it if f and any(v is not None for v in f)]


def agrupar(filas, dimensiones, valor):
    """Junta por dimensiones y devuelve (consistentes, ambiguas)."""
    grupos = defaultdict(set)
    for f in filas:
        grupos[tuple(_t(f.get(d)) for d in dimensiones)].add(valor(f))
    consistentes = {k: next(iter(v)) for k, v in grupos.items() if len(v) == 1}
    ambiguas = {k: v for k, v in grupos.items() if len(v) > 1}
    return consistentes, ambiguas


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quincena", required=True, help="primer día de la quincena, AAAA-MM-DD")
    ap.add_argument("--aplicar", action="store_true", help="escribir de verdad")
    args = ap.parse_args()

    from datetime import date
    quincena = date.fromisoformat(args.quincena)
    etq = etiqueta(quincena)

    if not EXCEL.exists():
        print("No encuentro %s. Está fuera de git: ver fuentes/LEEME.md." % EXCEL)
        return 1
    if args.aplicar and settings.db_propia_name != "testing":
        print("La base propia es %r. Este script sólo escribe en 'testing'."
              % settings.db_propia_name)
        return 1

    wb = openpyxl.load_workbook(EXCEL, read_only=True, data_only=True)
    db = SessionPropia()
    servicio = TarifarioService(db)
    print("Quincena %s (%s) — %s\n" % (etq, quincena,
                                       "APLICANDO" if args.aplicar else "simulación"))

    total, saltadas = 0, []

    # ─── Viajes ─────────────────────────────────────────────────────────────
    viajes = [f for f in leer(wb, "Viajes") if _t(f.get("Quincena_Liq")) == etq]
    dims = ("Colectivo_Unificado", "cliente", "finca", "nombre_capataz")
    reglas, ambiguas = agrupar(
        viajes, dims, lambda f: (_d(f.get("Precio_Viaje")), _t(f.get("Tipo_Viaje")).upper()))
    print("VIAJES: %d filas → %d reglas, %d combinaciones ambiguas"
          % (len(viajes), len(reglas), len(ambiguas)))
    for (tercero, cliente, finca, capataz), (precio, tipo) in reglas.items():
        if precio is None:
            saltadas.append(("viajes", "sin precio", tercero, cliente, finca, capataz))
            continue
        if args.aplicar:
            try:
                servicio.crear("viajes", quincena, {
                    "tercero": tercero, "cliente": cliente, "finca": finca,
                    "capataz": capataz, "precio": precio,
                    "tipo_viaje": tipo if tipo in ("CORTO", "LARGO") else None,
                })
            except TarifaInvalida as e:
                saltadas.append(("viajes", str(e)[:50], tercero, cliente, finca, capataz))
                continue
        total += 1
    for k, v in ambiguas.items():
        saltadas.append(("viajes", "dos precios: %s" % sorted(str(x[0]) for x in v)) + k)

    # ─── Combustible ────────────────────────────────────────────────────────
    comb = [f for f in leer(wb, "Combustible") if _t(f.get("Quincena_Liq")) == etq]
    reglas, ambiguas = agrupar(comb, ("Colectivo_Unificado",),
                               lambda f: _d(f.get("Precio_Combustible")))
    print("COMBUSTIBLE: %d filas → %d precios, %d dueños ambiguos"
          % (len(comb), len(reglas), len(ambiguas)))
    for (tercero,), precio in reglas.items():
        if precio is None or not tercero:
            saltadas.append(("combustible", "sin precio o sin dueño", tercero, "", "", ""))
            continue
        if args.aplicar:
            try:
                servicio.crear("combustible", quincena, {"tercero": tercero, "precio": precio})
            except TarifaInvalida as e:
                saltadas.append(("combustible", str(e)[:50], tercero, "", "", ""))
                continue
        total += 1
    for (tercero,), v in ambiguas.items():
        saltadas.append(("combustible", "dos precios: %s" % sorted(str(x) for x in v),
                         tercero, "", "", ""))

    # ─── Seguros ────────────────────────────────────────────────────────────
    seg = [f for f in leer(wb, "Seguros") if _t(f.get("Quincena_mes")) == etq]
    print("SEGUROS: %d filas" % len(seg))
    for f in seg:
        tercero, importe = _t(f.get("Colectivo")), _d(f.get("Monto_Seguro"))
        if not tercero or importe is None:
            continue
        if args.aplicar:
            try:
                # El Excel guarda el seguro por dueño, sin decir de qué máquina
                # es ni de qué tipo. Se carga como AUTOMOTOR con el sujeto en el
                # mismo nombre: es lo único que el origen dice, y rellenarlo con
                # otra cosa sería inventar.
                servicio.crear("seguros", quincena, {
                    "tercero": tercero, "tipo_seguro": "AUTOMOTOR",
                    "sujeto": tercero, "importe": importe})
            except TarifaInvalida as e:
                saltadas.append(("seguros", str(e)[:50], tercero, "", "", ""))
                continue
        total += 1

    # ─── Horas de reparación ────────────────────────────────────────────────
    # El Excel tiene un solo valor de hora para todos, con vigencia desde una
    # fecha. El tarifario lo quiere por tercero, así que se le carga el mismo
    # precio a cada tercero que tuvo horas en la quincena.
    ws = wb["Precios_Hora"]
    precio_hora = None
    for fila in ws.iter_rows(values_only=True):
        if fila and isinstance(fila[-1], (int, float)):
            precio_hora = Decimal(str(fila[-1]))
    liq = db.query(Liquidacion).filter(Liquidacion.quincena == quincena).first()
    terceros_taller = sorted({
        r.tercero for r in db.query(HoraReparacion)
        .filter(HoraReparacion.liquidacion_id == (liq.id if liq else -1)).all()
        if r.tercero
    })
    print("REPARACIÓN: precio de la hora %s → %d tercero(s) con horas en la quincena"
          % (precio_hora, len(terceros_taller)))
    if precio_hora is not None:
        for tercero in terceros_taller:
            if args.aplicar:
                try:
                    servicio.crear("reparacion", quincena,
                                   {"tercero": tercero, "precio": precio_hora})
                except TarifaInvalida as e:
                    saltadas.append(("reparacion", str(e)[:50], tercero, "", "", ""))
                    continue
            total += 1

    # ─── Qué no entró ───────────────────────────────────────────────────────
    print("\n%s %d tarifas." % ("Cargadas" if args.aplicar else "Se cargarían", total))
    if saltadas:
        print("\nNO se importan %d, y el motivo:" % len(saltadas))
        for s in saltadas:
            tipo, motivo = s[0], s[1]
            quien = " | ".join(x for x in s[2:] if x)
            print("   [%-12s] %-46s %s" % (tipo, motivo[:46], quien[:70]))
        print("\nNinguna se adivina: cuando una combinación tiene dos precios en la")
        print("misma quincena, el que decide cuál vale es el liquidador.")

    if args.aplicar:
        print("\nResumen del tarifario:")
        for t, r in servicio.resumen(quincena).items():
            print("   %-12s cargadas=%-4d sin confirmar=%d" % (t, r["cargadas"], r["heredadas"]))

    db.close()
    wb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
