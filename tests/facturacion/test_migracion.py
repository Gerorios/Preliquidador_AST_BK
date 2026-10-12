"""Las migraciones de Facturación: la 001 creó facturacion_tarea y la 002 la borra.

Se leen los `.sql` como texto, sin base, como en tests/core/test_migracion_roles.py.
Desde el 2026-10-12 la Unidad sugerida se lee del sistema de campo
(docs/superpowers/plans/2026-10-12-unidad-desde-campo.md): la tabla sale del
modelo y ningún código la lee, así que el backend de esta versión arranca con
la tabla todavía en la base y la 002 se aplica después del reinicio.
"""
import re
from pathlib import Path

import pytest

# Importar app.main registra en Base.metadata las tablas del núcleo y las de
# los módulos activos, igual que al arrancar la app.
import app.main  # noqa: F401
from app.core.database import Base

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "migrations" / "facturacion"
M001 = CARPETA / "001_unidad_por_tarea.sql"
M002 = CARPETA / "002_borrar_unidad_por_tarea.sql"
ORDEN = RAIZ / "migrations" / "ORDEN.txt"


def _sql(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sentencias(sql: str) -> list[str]:
    """Corta como el aplicador (por `;`, salteando los trozos que son sólo
    comentarios) y deja cada sentencia sin sus líneas de comentario y con los
    espacios colapsados."""
    sentencias = []
    for trozo in sql.split(";"):
        lineas = [
            linea.strip() for linea in trozo.splitlines()
            if linea.strip() and not linea.strip().startswith("--")
        ]
        if lineas:
            sentencias.append(re.sub(r"\s+", " ", " ".join(lineas)))
    return sentencias


# 1. La trampa del aplicador: corta el archivo por `;`, así que lo que siga a un
#    `;` en una línea comentada quedaría sin `--` y se ejecutaría.

@pytest.mark.parametrize("ruta", [M001, M002], ids=["001", "002"])
def test_ninguna_linea_comentada_tiene_punto_y_coma(ruta):
    malas = [
        linea for linea in _sql(ruta).splitlines()
        if linea.strip().startswith("--") and ";" in linea
    ]
    assert malas == []


# 2. La 002 borra los permisos guardados de `unidad` y la tabla, y nada más.

def test_sentencias_de_la_002():
    assert _sentencias(_sql(M002)) == [
        "DELETE FROM rol_permiso WHERE modulo = 'facturacion' AND pantalla = 'unidad'",
        "DROP TABLE IF EXISTS facturacion_tarea",
    ]


# 3. La 002 va con el deploy, después del reinicio del backend.

def test_la_002_no_es_diferible():
    assert "-- NO DIFERIBLE" in _sql(M002)


# 4. En una base nueva corre la 001 y después la 002, que la borra. No se pide
#    que la 002 sea la última: la E2 suma la 003.

def test_la_002_va_despues_de_la_001_en_orden():
    entradas = [
        linea.split()[0] for linea in _sql(ORDEN).splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]
    assert "facturacion/001_unidad_por_tarea.sql" in entradas
    assert "facturacion/002_borrar_unidad_por_tarea.sql" in entradas
    assert (
        entradas.index("facturacion/002_borrar_unidad_por_tarea.sql")
        > entradas.index("facturacion/001_unidad_por_tarea.sql")
    )


# 5. El modelo ya no declara la tabla: el chequeo de tablas del arranque no la
#    pide, y el backend arranca con o sin ella en la base.

def test_el_modelo_no_declara_facturacion_tarea():
    assert "facturacion_tarea" not in Base.metadata.tables


# 6. El código nuevo no lee la tabla: si la leyera, la 002 lo rompería.

def test_ningun_py_de_app_ni_de_scripts_nombra_la_tabla():
    nombran = [
        str(ruta.relative_to(RAIZ))
        for carpeta in ("app", "scripts")
        for ruta in (RAIZ / carpeta).rglob("*.py")
        if "facturacion_tarea" in ruta.read_text(encoding="utf-8")
    ]
    assert nombran == []
