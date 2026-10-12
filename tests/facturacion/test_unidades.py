"""Las nueve Unidades de facturación (plan de la E1, D5).

Fijan el vocabulario que comparten la Unidad sugerida de cada tarea (E1) y la
Unidad de facturación de cada Línea de comprobante (E2). En la base se guarda
la clave; la etiqueta vive en el código. El front tiene un espejo en
src/modulos/facturacion/unidades.js, con su propio test que fija lo mismo.
"""
import pytest

from app.modulos.facturacion.unidades import (
    ETIQUETAS,
    NO_FACTURABLE_PLANILLA,
    UNIDAD_DE_PLANILLA,
    UNIDADES,
    UNIDADES_COSECHA,
    normalizar_texto,
    traducir_unidad,
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


def test_cada_texto_de_la_planilla_es_una_de_las_nueve():
    for clave in UNIDAD_DE_PLANILLA.values():
        assert clave in UNIDADES


# La traducción del texto de unidad que trae el sistema de campo (tercer
# segmento de la descripción de la tarea) a la clave de la Unidad sugerida.

@pytest.mark.parametrize("texto, clave", [
    ("HORAS PEON", "horas_peon"),
    ("HORAS TRACTOR", "horas_tractor"),
    ("PLANTA", "plantas"),
    ("HECTAREA", "hectareas"),
    ("TANCADA", "tancadas"),
    ("BINS", "bins"),
    ("BINS C", "bins_c"),
    ("BINS M", "bins_m"),
    ("VIAJES", "viajes"),
])
def test_traduce_los_nueve_textos_a_su_clave(texto, clave):
    assert traducir_unidad(texto) == (clave, False)


def test_no_facturable_es_la_marca_sin_unidad():
    assert traducir_unidad("NO FACTURABLE") == (None, True)


@pytest.mark.parametrize("texto", ["", "   ", None])
def test_lo_vacio_queda_sin_definir(texto):
    assert traducir_unidad(texto) == (None, False)


@pytest.mark.parametrize("texto", ["HORA PEON", "KILOS", "HECTAREAS"])
def test_lo_desconocido_queda_sin_definir(texto):
    assert traducir_unidad(texto) == (None, False)


@pytest.mark.parametrize("texto, esperado", [
    (" horas  peón ", ("horas_peon", False)),
    ("Hectárea", ("hectareas", False)),
    ("bins c", ("bins_c", False)),
    ("no  facturable", (None, True)),
])
def test_tolera_acentos_espacios_y_minusculas(texto, esperado):
    assert traducir_unidad(texto) == esperado


def test_bins_c_no_se_confunde_con_bins():
    assert traducir_unidad("bins c") != ("bins", False)


def test_normalizar_texto():
    assert normalizar_texto(" Horas  Peón ") == "HORAS PEON"
    assert normalizar_texto(None) == ""
