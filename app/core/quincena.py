"""
Utilidad de Quincena, compartida por todos los módulos (ver CONTEXT.md).
1ra quincena = días 1 a 15; 2da = 16 a fin de mes. Se identifica por su
fecha de inicio.
"""
import calendar
from datetime import date


def calcular_rango_quincena(quincena: date) -> tuple[date, date]:
    if quincena.day == 1:
        return quincena, quincena.replace(day=15)
    else:
        ultimo_dia = calendar.monthrange(quincena.year, quincena.month)[1]
        return quincena.replace(day=16), quincena.replace(day=ultimo_dia)
