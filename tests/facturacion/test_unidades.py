"""Las nueve Unidades de facturación (plan de la E1, D5).

Fijan el vocabulario que comparten la Unidad sugerida de cada tarea (E1) y la
Unidad de facturación de cada Línea de comprobante (E2). En la base se guarda
la clave; la etiqueta vive en el código. El front tiene un espejo en
src/modulos/facturacion/unidades.js, con su propio test que fija lo mismo.
"""
from app.modulos.facturacion.unidades import (
    ETIQUETAS,
    NO_FACTURABLE_PLANILLA,
    UNIDAD_DE_PLANILLA,
    UNIDADES,
    UNIDADES_COSECHA,
)


def test_son_las_nueve_claves_en_orden():
    assert UNIDADES == (
        "horas_peon", "horas_tractor", "plantas", "hectareas", "tancadas",
        "bins", "bins_c", "bins_m", "viajes",
    )


def test_las_de_cosecha_son_las_ultimas_cuatro():
    assert UNIDADES_COSECHA == ("bins", "bins_c", "bins_m", "viajes")
    assert UNIDADES_COSECHA == UNIDADES[-4:]


def test_cada_unidad_tiene_su_etiqueta():
    assert ETIQUETAS == {
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
    assert tuple(ETIQUETAS) == UNIDADES


def test_la_planilla_traduce_los_nueve_textos():
    assert UNIDAD_DE_PLANILLA == {
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
    assert set(UNIDAD_DE_PLANILLA.values()) == set(UNIDADES)


def test_no_facturable_es_la_marca_y_no_una_unidad():
    assert NO_FACTURABLE_PLANILLA == "NO FACTURABLE"
    assert NO_FACTURABLE_PLANILLA not in UNIDAD_DE_PLANILLA
    assert "no_facturable" not in UNIDADES
