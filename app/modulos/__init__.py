"""Registro de módulos del sistema. Agregar un módulo = una línea acá."""
from app.modulos.preliquidacion import MODULO as PRELIQUIDACION

REGISTRO = (PRELIQUIDACION,)


def activos():
    return tuple(m for m in REGISTRO if m.activo)


def claves():
    return tuple(m.clave for m in REGISTRO)
