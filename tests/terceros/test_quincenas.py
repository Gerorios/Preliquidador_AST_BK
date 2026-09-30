"""La Quincena como la escribe y la ofrece el módulo."""
from datetime import date

import pytest

from app.modulos.terceros.services import quincenas


@pytest.mark.parametrize("dia,etiqueta", [
    (1, "08-1Q"), (15, "08-1Q"), (16, "08-2Q"), (31, "08-2Q"),
])
def test_la_etiqueta_es_la_notacion_del_excel(dia, etiqueta):
    assert quincenas.etiqueta(date(2026, 8, dia)) == etiqueta


def test_el_mes_va_con_cero_adelante():
    """El Excel escribe '03-1Q', no '3-1Q': si no coincide, no cruza."""
    assert quincenas.etiqueta(date(2026, 3, 1)) == "03-1Q"


@pytest.mark.parametrize("dia,nombre", [
    (1, "1ra de agosto 2026"), (16, "2da de agosto 2026"),
])
def test_el_nombre_se_lee_sin_traducir(dia, nombre):
    assert quincenas.nombre(date(2026, 8, dia)) == nombre


@pytest.mark.parametrize("dia,inicio", [(1, 1), (15, 1), (16, 16), (31, 16)])
def test_una_fecha_cualquiera_cae_en_su_quincena(dia, inicio):
    assert quincenas.inicio_de_quincena(date(2026, 8, dia)) == date(2026, 8, inicio)


@pytest.mark.parametrize("dia,valido", [(1, True), (16, True), (2, False), (15, False), (31, False)])
def test_una_quincena_se_identifica_por_su_primer_dia(dia, valido):
    assert quincenas.es_inicio_valido(date(2026, 8, dia)) is valido


def test_la_anterior_a_una_segunda_es_la_primera_del_mismo_mes():
    assert quincenas.anterior(date(2026, 8, 16)) == date(2026, 8, 1)


def test_la_anterior_a_una_primera_es_la_segunda_del_mes_pasado():
    assert quincenas.anterior(date(2026, 8, 1)) == date(2026, 7, 16)


def test_la_anterior_cruza_el_año():
    assert quincenas.anterior(date(2026, 1, 1)) == date(2025, 12, 16)


def test_la_anterior_a_marzo_cae_en_febrero_sin_importar_su_largo():
    assert quincenas.anterior(date(2027, 3, 1)) == date(2027, 2, 16)
    assert quincenas.anterior(date(2028, 3, 1)) == date(2028, 2, 16)


def test_las_recientes_van_de_la_mas_nueva_a_la_mas_vieja():
    lista = quincenas.recientes(hasta=date(2026, 8, 20), cantidad=4)
    assert lista == [date(2026, 8, 16), date(2026, 8, 1), date(2026, 7, 16), date(2026, 7, 1)]


def test_las_recientes_incluyen_la_quincena_en_curso():
    """El liquidador mira la quincena abierta, no solo las cerradas."""
    assert quincenas.recientes(hasta=date(2026, 8, 3), cantidad=1) == [date(2026, 8, 1)]


def test_dos_años_de_quincenas_son_cuarenta_y_ocho():
    lista = quincenas.recientes(hasta=date(2026, 12, 16), cantidad=48)
    assert len(lista) == len(set(lista)) == 48
    assert lista[-1] == date(2025, 1, 1)


def test_la_siguiente_de_la_1ra_es_la_2da_del_mismo_mes():
    from app.modulos.terceros.services.quincenas import siguiente
    assert siguiente(date(2026, 8, 1)) == date(2026, 8, 16)


def test_la_siguiente_de_la_2da_de_diciembre_es_la_1ra_de_enero():
    from app.modulos.terceros.services.quincenas import siguiente
    assert siguiente(date(2026, 12, 16)) == date(2027, 1, 1)


def test_siguiente_y_anterior_son_inversas():
    from app.modulos.terceros.services.quincenas import anterior, siguiente
    q = date(2026, 1, 1)
    for _ in range(30):
        assert anterior(siguiente(q)) == q
        q = siguiente(q)
