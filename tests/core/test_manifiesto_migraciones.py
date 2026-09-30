"""El manifiesto `migrations/ORDEN.txt` cubre todas las migraciones.

Cada `*.sql` bajo `migrations/` figura exactamente una vez; el manifiesto no
nombra archivos que no existen; y las entradas `historica` (ya contenidas en
`preliquidacion/000_esquema_base.sql`, exportado de producción) van después de
ese archivo.
"""
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "migrations"
MANIFIESTO = MIGRACIONES / "ORDEN.txt"
BASE = "preliquidacion/000_esquema_base.sql"
MARCAS_VALIDAS = {"historica"}


def _entradas() -> list[tuple[str, set[str]]]:
    """(ruta relativa a migrations/, marcas) por cada línea útil del
    manifiesto. Se ignoran líneas vacías y comentarios (`#`)."""
    entradas = []
    for linea in MANIFIESTO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        ruta, *marcas = linea.split()
        entradas.append((ruta, set(marcas)))
    return entradas


def _sql_en_disco() -> set[str]:
    return {p.relative_to(MIGRACIONES).as_posix() for p in MIGRACIONES.rglob("*.sql")}


def test_manifiesto_existe():
    assert MANIFIESTO.is_file(), "falta migrations/ORDEN.txt"


def test_cada_sql_figura_exactamente_una_vez():
    rutas = [ruta for ruta, _ in _entradas()]
    repetidas = sorted(r for r, n in Counter(rutas).items() if n > 1)
    assert repetidas == [], f"entradas repetidas en ORDEN.txt: {repetidas}"
    faltantes = sorted(_sql_en_disco() - set(rutas))
    assert faltantes == [], f"migraciones que no están en ORDEN.txt: {faltantes}"


def test_manifiesto_no_nombra_archivos_inexistentes():
    inexistentes = sorted(
        ruta for ruta, _ in _entradas() if not (MIGRACIONES / ruta).is_file()
    )
    assert inexistentes == [], f"ORDEN.txt nombra archivos que no existen: {inexistentes}"


def test_marcas_conocidas():
    raras = sorted(
        (ruta, sorted(marcas - MARCAS_VALIDAS))
        for ruta, marcas in _entradas()
        if marcas - MARCAS_VALIDAS
    )
    assert raras == [], f"marcas desconocidas en ORDEN.txt: {raras}"


def test_historicas_van_despues_del_esquema_base():
    rutas = [ruta for ruta, _ in _entradas()]
    assert BASE in rutas
    pos_base = rutas.index(BASE)
    antes = [
        ruta
        for i, (ruta, marcas) in enumerate(_entradas())
        if "historica" in marcas and i < pos_base
    ]
    assert antes == [], f"históricas antes de {BASE}: {antes}"
