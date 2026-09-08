"""Registro de módulos del sistema. Agregar un módulo = una línea acá."""
from app.modulos.preliquidacion import MODULO as PRELIQUIDACION
from app.modulos.fletes import MODULO as FLETES

REGISTRO = (PRELIQUIDACION, FLETES)


def activos():
    return tuple(m for m in REGISTRO if m.activo)


def claves():
    return tuple(m.clave for m in REGISTRO)
