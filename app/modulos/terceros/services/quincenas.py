"""La Quincena vista desde este módulo: cómo se escribe y cuáles se ofrecen.

El corte es el del Sistema (`app.core.quincena`): 1ra del 1 al 15, 2da del 16 a
fin de mes. Lo que agrega el módulo es la **notación del Excel de origen**
(`08-1Q`), que no es un detalle de presentación: es la clave con la que se
compara contra las hojas del Excel mientras el módulo conviva con él, y la que
el liquidador lee todos los días.

Vive en el módulo y no en el núcleo porque hoy la usa un solo módulo
(regla 4 de GUIA-MODULOS: el núcleo crece cuando dos la necesitan).
"""
from datetime import date, timedelta

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def es_primera(f: date) -> bool:
    return f.day <= 15


def etiqueta(f: date) -> str:
    """La notación del Excel: '08-1Q' es la 1ra quincena de agosto."""
    return f"{f.month:02d}-{1 if es_primera(f) else 2}Q"


def nombre(f: date) -> str:
    """'1ra de agosto 2026', para que se lea sin traducir del código."""
    return f"{'1ra' if es_primera(f) else '2da'} de {MESES[f.month - 1]} {f.year}"


def inicio_de_quincena(f: date) -> date:
    """La fecha con la que se identifica la quincena que contiene a `f`."""
    return f.replace(day=1 if es_primera(f) else 16)


def es_inicio_valido(f: date) -> bool:
    """Una quincena se identifica por su primer día: el 1 o el 16."""
    return f.day in (1, 16)


def anterior(quincena: date) -> date:
    """La quincena inmediatamente anterior a una dada."""
    if quincena.day == 16:
        return quincena.replace(day=1)
    ultimo_del_mes_anterior = quincena.replace(day=1) - timedelta(days=1)
    return ultimo_del_mes_anterior.replace(day=16)


def recientes(hasta: date | None = None, cantidad: int = 24) -> list[date]:
    """Las últimas `cantidad` quincenas, de la más nueva a la más vieja.

    Se calculan, no se leen de ninguna tabla: el módulo todavía no tiene tablas
    propias (llegan en la etapa 4) y una quincena existe por el calendario, no
    porque alguien la haya dado de alta.
    """
    resultado = [inicio_de_quincena(hasta or date.today())]
    for _ in range(cantidad - 1):
        resultado.append(anterior(resultado[-1]))
    return resultado
