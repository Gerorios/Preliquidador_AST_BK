"""
Utilidad de Quincena, compartida por todos los módulos (ver CONTEXT.md).
1ra quincena = días 1 a 15; 2da = 16 a fin de mes. Se identifica por su
fecha de inicio.
"""
import calendar
from datetime import date
from typing import Annotated

from pydantic import AfterValidator


def validar_quincena(quincena: date) -> date:
    """Rechaza toda fecha que no sea inicio de quincena. Se rechaza en vez de
    normalizar: `calcular_rango_quincena` toma cualquier día distinto de 1 como
    segunda quincena, pero `Preliquidacion.quincena` es la fecha cruda, así que
    un 17 creaba una segunda preliquidación con las mismas líneas que la del 16.
    Una fecha así viene de un cliente que está mal, y normalizarla lo escondería."""
    if quincena.day not in (1, 16):
        raise ValueError(
            f"La quincena debe empezar el 1 o el 16 del mes, no el {quincena.day}"
        )
    return quincena


# Tipo para esquemas Pydantic (`quincena: Quincena`) y parámetros de FastAPI.
# OJO en los parámetros Query: escribirlo `q: Annotated[Quincena, Query()]`.
# Con `q: Quincena = Query(...)` FastAPI 0.136 descarta el validador y un 17
# pasa sin error (comprobado; el test de API de copiar lo cubre).
Quincena = Annotated[date, AfterValidator(validar_quincena)]


def calcular_rango_quincena(quincena: date) -> tuple[date, date]:
    if quincena.day == 1:
        return quincena, quincena.replace(day=15)
    else:
        ultimo_dia = calendar.monthrange(quincena.year, quincena.month)[1]
        return quincena.replace(day=16), quincena.replace(day=ultimo_dia)
