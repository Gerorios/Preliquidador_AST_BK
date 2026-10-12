"""Las nueve Unidades de facturación (docs/modulos/facturacion/CONTEXT-facturacion.md).

Son el vocabulario de la Unidad sugerida de cada tarea (E1) y de la Unidad de
facturación de cada Línea de comprobante (E2). En la base se guarda la clave;
la etiqueta vive sólo acá. El front tiene un espejo en
src/modulos/facturacion/unidades.js: si cambia una, cambia la otra.
"""

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

# Las de cosecha son las últimas cuatro. En la E1 una tarea con una de ellas
# cuenta como con unidad; sacarlas del Cruce y de las Alertas es de la E3.
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

# Cómo escribe cada unidad la planilla de las contadoras (el maestro de tareas
# de la primera carga y la columna UM de la hoja de facturación).
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
# la tarea, que se guarda aparte de la Unidad sugerida.
NO_FACTURABLE_PLANILLA = "NO FACTURABLE"
