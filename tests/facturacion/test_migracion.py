"""La migración facturacion/001 dice lo mismo que el modelo.

Se lee el `.sql` como texto, sin base, como en tests/core/test_migracion_roles.py
(partes c y d): la tabla tiene que tener las columnas del modelo, y el archivo
tiene que ser seguro de aplicar con el método que lo corta por `;`.
"""
import re
from pathlib import Path

import app.modulos.facturacion.models  # noqa: F401  (registra facturacion_tarea)
from app.core.database import Base

RAIZ = Path(__file__).resolve().parents[2]
MIGRACION = RAIZ / "migrations" / "facturacion" / "001_unidad_por_tarea.sql"

CREATE_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\)\s*ENGINE", re.IGNORECASE | re.DOTALL
)
NO_SON_COLUMNAS = {"UNIQUE", "CONSTRAINT", "PRIMARY", "KEY", "INDEX", "FOREIGN"}


def _sql() -> str:
    return MIGRACION.read_text(encoding="utf-8")


# (c) Las columnas de cada CREATE TABLE son las del modelo.

def test_columnas_de_la_tabla_coinciden_con_el_modelo():
    tablas = {}
    for nombre, cuerpo in CREATE_TABLE.findall(_sql()):
        columnas = set()
        for linea in cuerpo.splitlines():
            linea = linea.strip()
            if linea.startswith("--"):
                continue
            palabras = linea.split()
            if palabras and palabras[0].upper() not in NO_SON_COLUMNAS:
                columnas.add(palabras[0])
        tablas[nombre] = columnas
    assert set(tablas) == {"facturacion_tarea"}
    for nombre, columnas in tablas.items():
        del_modelo = set(Base.metadata.tables[nombre].columns.keys())
        assert columnas == del_modelo, nombre


# (d) La trampa del aplicador.

def test_ninguna_linea_comentada_tiene_texto_despues_de_un_punto_y_coma():
    # El aplicador corta el archivo por `;`: lo que siga a un `;` en una línea
    # comentada quedaría sin `--` y se ejecutaría.
    malas = [
        linea for linea in _sql().splitlines()
        if linea.strip().startswith("--") and re.search(r";\s*\S", linea)
    ]
    assert malas == []
