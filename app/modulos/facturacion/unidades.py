"""Las nueve Unidades de facturación (docs/modulos/facturacion/CONTEXT-facturacion.md).

Son el vocabulario de la Unidad sugerida de cada tarea, que se lee en vivo del
sistema de campo, y de la Unidad de facturación de cada Línea de comprobante
(E2). En la base se guarda la clave; la etiqueta vive sólo acá. El front
tiene un espejo en src/modulos/facturacion/unidades.js: si cambia una, cambia
la otra.
"""

import unicodedata

# Las claves, en el orden en que se muestran. No cambian: se guardan en la base.
UNIDADES = (
    "horas_peon",
    "horas_tractor",
    "plantas",
    "hectareas",
    "tancadas",
    "bins",
    "bins_c",
    "bins_m",
    "viajes",
)

# Las de cosecha son las últimas cuatro. Una tarea con una de ellas cuenta como
# con unidad; sacarlas del Cruce y de las Alertas es de la E3.
UNIDADES_COSECHA = UNIDADES[-4:]

ETIQUETAS = {
    "horas_peon": "Horas de peón",
    "horas_tractor": "Horas de tractor",
    "plantas": "Plantas",
    "hectareas": "Hectáreas",
    "tancadas": "Tancadas",
    "bins": "Bins",
    "bins_c": "Bins C",
    "bins_m": "Bins M",
    "viajes": "Viajes",
}

# Cómo se escribe cada unidad en el sistema de campo (tercer segmento de la
# descripción de la tarea) y en la columna UM de la hoja de facturación.
UNIDAD_DE_PLANILLA = {
    "HORAS PEON": "horas_peon",
    "HORAS TRACTOR": "horas_tractor",
    "PLANTA": "plantas",
    "HECTAREA": "hectareas",
    "TANCADA": "tancadas",
    "BINS": "bins",
    "BINS C": "bins_c",
    "BINS M": "bins_m",
    "VIAJES": "viajes",
}

# "NO FACTURABLE" en la planilla no es una unidad: es la marca No facturable de
# la tarea, que deja la tarea sin Unidad sugerida.
NO_FACTURABLE_PLANILLA = "NO FACTURABLE"


def normalizar_texto(texto) -> str:
    """Sin acentos (NFKD), con los espacios colapsados y en mayúsculas; None da ""."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_acentos.split()).upper()


def traducir_unidad(texto) -> tuple[str | None, bool]:
    """(clave, False) si es una de las nueve; (None, True) si es NO FACTURABLE;
    (None, False) si está vacío o no se conoce: Sin definir.

    Compara el texto normalizado contra UNIDAD_DE_PLANILLA tal cual, sin alias:
    un texto que no coincide se corrige en la app de campo."""
    normalizado = normalizar_texto(texto)
    if normalizado == NO_FACTURABLE_PLANILLA:
        return None, True
    return UNIDAD_DE_PLANILLA.get(normalizado), False
