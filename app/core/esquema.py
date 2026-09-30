"""Comparación del modelo (ORM) contra el esquema real de la base propia.

Detecta un deploy incompleto: código que necesita una tabla o una columna que
la base todavía no tiene porque la migración no se aplicó. No guarda nada en
la base: sólo compara lo que declara el modelo con lo que la base tiene hoy.

El metadata llega por parámetro y no se importa acá: el núcleo no conoce a
los módulos (ADR-0013), y quien llama ya registró sus modelos.
"""
from dataclasses import dataclass, field

from sqlalchemy import MetaData
from sqlalchemy.engine.reflection import Inspector


@dataclass
class Diferencias:
    """Lo que el modelo pide y la base no tiene. Listas ordenadas para que el
    mensaje del arranque sea estable entre corridas."""
    tablas_faltantes: list[str] = field(default_factory=list)
    columnas_faltantes: list[str] = field(default_factory=list)  # "tabla.columna"


def comparar_esquema(metadata: MetaData, inspector: Inspector) -> Diferencias:
    """Compara sólo nombres de tablas y columnas.

    - Lo que sobra en la base no es error: producción puede tener columnas
      viejas deprecadas y `testing` tiene tablas de otros sistemas.
    - No compara tipos ni índices: MySQL y el ORM los describen distinto y
      darían falsos positivos.
    - De una tabla faltante no se listan sus columnas: el aviso ya es la tabla.
    """
    existentes = set(inspector.get_table_names())
    tablas_faltantes: list[str] = []
    columnas_faltantes: list[str] = []

    for nombre, tabla in metadata.tables.items():
        if nombre not in existentes:
            tablas_faltantes.append(nombre)
            continue
        en_base = {c["name"] for c in inspector.get_columns(nombre)}
        columnas_faltantes.extend(
            f"{nombre}.{col.name}" for col in tabla.columns if col.name not in en_base
        )

    return Diferencias(sorted(tablas_faltantes), sorted(columnas_faltantes))
