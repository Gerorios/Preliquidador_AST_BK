"""Migración del histórico: lectura de la planilla (plan de la E2, sección 3.1,
"Migración del histórico", y par C1 de la sección 3.9).

Lo que cuidan estos tests:
- que un número es-AR se lea igual venga como venga ("1.234,56", "$ 1.234,56",
  "1234"), porque la conciliación por Cliente y mes compara sumas al centavo;
- que lo que no es un número ("-", "#VALUE!", más decimales que la columna) se
  marque ilegible en vez de leerse como otra cosa: así su grupo se omite y se
  lista, y nunca se migra un importe adivinado;
- que el CSV se lea con BOM, CRLF y `;`, que es como lo puede dejar Excel;
- que un encabezado faltante frene con un error que lo nombre.

Datos inventados.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.modulos.facturacion.services.historico import (
    ENCABEZADOS,
    FilaPlanilla,
    NumeroDemasiadoLargo,
    PlanillaInvalida,
    ValorIlegible,
    leer_fecha,
    leer_numero_ar,
    leer_numero_comprobante,
    leer_planilla,
    leer_unidad,
)


# ─── Números es-AR ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("1.234,56", Decimal("1234.56")),
    ("1234,5", Decimal("1234.5")),
    ("12,5", Decimal("12.5")),
    ("1234", Decimal("1234")),
    ("$1.234,56", Decimal("1234.56")),
    ("$ 1.234,56", Decimal("1234.56")),
    # Sin coma, los puntos son de miles en grupos de 3 dígitos.
    ("1.234", Decimal("1234")),
    ("1.234.567", Decimal("1234567")),
    ("1.234.567,89", Decimal("1234567.89")),
    ("  12,5  ", Decimal("12.5")),
    ("0", Decimal("0")),
    # El negativo se lee: omitir su grupo es de la clasificación (pregunta 7).
    ("-1.234,56", Decimal("-1234.56")),
    ("$ -1.234,56", Decimal("-1234.56")),
    ("-$ 1.234,56", Decimal("-1234.56")),
])
def test_leer_numero_ar_lee_los_formatos_de_la_planilla(texto, esperado):
    assert leer_numero_ar(texto, decimales=2) == esperado


@pytest.mark.parametrize("texto", [
    "-",
    "#VALUE!",
    "$ -",
    "abc",
    "1,2,3",
    "1.23,4",
    "12.5",
    "1.2.3",
    "1..234",
    "$",
])
def test_leer_numero_ar_marca_ilegible_lo_que_no_es_un_numero(texto):
    with pytest.raises(ValorIlegible):
        leer_numero_ar(texto, decimales=2)


def test_leer_numero_ar_con_mas_decimales_que_la_columna_es_ilegible():
    # El importe y la cantidad tienen 2 decimales; el precio, 4.
    with pytest.raises(ValorIlegible):
        leer_numero_ar("1.234,567", decimales=2)
    assert leer_numero_ar("1.234,567", decimales=4) == Decimal("1234.567")
    with pytest.raises(ValorIlegible):
        leer_numero_ar("0,12345", decimales=4)


@pytest.mark.parametrize("texto", ["", "   ", None])
def test_leer_numero_ar_vacio_da_none(texto):
    # Vacío no es ilegible: qué hace cada columna con un vacío lo decide la
    # clasificación (par C3).
    assert leer_numero_ar(texto, decimales=2) is None


# ─── Fechas ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("1/9/2025", date(2025, 9, 1)),
    ("16/09/2025", date(2025, 9, 16)),
    ("01/10/2026", date(2026, 10, 1)),
    ("1/9/25", date(2025, 9, 1)),
    ("16/12/26", date(2026, 12, 16)),
    ("  1/9/2025 ", date(2025, 9, 1)),
])
def test_leer_fecha_admite_anio_de_cuatro_y_de_dos_cifras(texto, esperado):
    assert leer_fecha(texto) == esperado


@pytest.mark.parametrize("texto", [
    "31/2/2025",
    "1/13/2025",
    "2025-09-01",
    "1/9",
    "1/9/202",
    "a/b/c",
    "-",
])
def test_leer_fecha_invalida_es_ilegible(texto):
    with pytest.raises(ValorIlegible):
        leer_fecha(texto)


@pytest.mark.parametrize("texto", ["", "   ", None])
def test_leer_fecha_vacia_da_none(texto):
    # FECHA FAC vacía es un caso real (unas 250 filas): no es un error.
    assert leer_fecha(texto) is None


# ─── Planilla ───────────────────────────────────────────────────────────────

ENCABEZADO = [
    "FECHA A FACTURAR", "QUINCENA A FACTURAR", "CLIENTE", "FINCA", "TAREA",
    "GRUPO TAREA", "UM", "CANT FACTURA", "PRECIO UNIT", "FACTURA", "FACT N°",
    "FECHA FAC", "Nosotros",
]


def _escribir(ruta, filas, separador, bom=True):
    texto = "\r\n".join(separador.join(f) for f in filas) + "\r\n"
    ruta.write_bytes(("﻿" if bom else "").encode("utf-8") + texto.encode("utf-8"))
    return ruta


def test_leer_planilla_con_bom_crlf_y_punto_y_coma(tmp_path):
    ruta = _escribir(tmp_path / "planilla.csv", [
        ENCABEZADO,
        ["1/9/2025", "1", "CLIENTE UNO", "", "TAREA A", "G", "PLANTA",
         "1.000", "12,5", "$ 12.500,00", "0001-00000010", "5/9/25", "nota"],
        ["16/9/2025", "2", "CLIENTE UNO", "FINCA X", "TAREA A", "G", "TANCADA",
         "3", "100", "300", "", "", ""],
    ], ";")

    filas = leer_planilla(ruta)

    assert filas == [
        FilaPlanilla(
            fila=2, fecha_a_facturar="1/9/2025", cliente="CLIENTE UNO", finca="",
            tarea="TAREA A", um="PLANTA", cantidad="1.000", precio="12,5",
            importe="$ 12.500,00", numero="0001-00000010", fecha_factura="5/9/25",
        ),
        FilaPlanilla(
            fila=3, fecha_a_facturar="16/9/2025", cliente="CLIENTE UNO",
            finca="FINCA X", tarea="TAREA A", um="TANCADA", cantidad="3",
            precio="100", importe="300", numero="", fecha_factura="",
        ),
    ]


def test_leer_planilla_con_comas_y_comillas(tmp_path):
    # El export de hoy: separado por comas, con los números entre comillas
    # porque llevan la coma decimal adentro.
    ruta = _escribir(tmp_path / "planilla.csv", [
        [f'"{e}"' for e in ENCABEZADO],
        ['"1/9/2025"', '"1"', '"CLIENTE UNO"', '""', '"TAREA A"', '"G"', '"PLANTA"',
         '"10"', '"1.234,56"', '"$ 12.345,60"', '"10"', '""', '""'],
    ], ",", bom=False)

    [fila] = leer_planilla(ruta)

    assert fila.cliente == "CLIENTE UNO"
    assert fila.precio == "1.234,56"
    assert fila.importe == "$ 12.345,60"
    assert fila.numero == "10"


def test_leer_planilla_busca_los_encabezados_recortados_y_en_mayusculas(tmp_path):
    encabezado = [f"  {e.lower()} " for e in ENCABEZADO]
    ruta = _escribir(tmp_path / "planilla.csv", [
        encabezado,
        ["1/9/2025", "1", "CLIENTE UNO", "", "TAREA A", "G", "PLANTA",
         "1", "2", "2", "10", "", ""],
    ], ";")

    [fila] = leer_planilla(ruta)

    assert fila.tarea == "TAREA A"
    assert fila.numero == "10"


def test_leer_planilla_con_un_encabezado_faltante_lo_nombra(tmp_path):
    sin_tarea = [e for e in ENCABEZADO if e != "TAREA"]
    ruta = _escribir(tmp_path / "planilla.csv", [sin_tarea], ";")

    with pytest.raises(PlanillaInvalida) as error:
        leer_planilla(ruta)

    assert "TAREA" in str(error.value)
    assert error.value.faltantes == ["TAREA"]


def test_leer_planilla_lista_todos_los_encabezados_faltantes(tmp_path):
    sin_dos = [e for e in ENCABEZADO if e not in ("UM", "FACT N°")]
    ruta = _escribir(tmp_path / "planilla.csv", [sin_dos], ",")

    with pytest.raises(PlanillaInvalida) as error:
        leer_planilla(ruta)

    assert error.value.faltantes == ["UM", "FACT N°"]
    assert "UM" in str(error.value) and "FACT N°" in str(error.value)


def test_los_encabezados_que_se_ignoran_no_son_obligatorios(tmp_path):
    # QUINCENA A FACTURAR, GRUPO TAREA y Nosotros se ignoran (sección 2.2).
    assert "GRUPO TAREA" not in ENCABEZADOS
    ruta = _escribir(tmp_path / "planilla.csv", [
        list(ENCABEZADOS),
        ["1/9/2025", "CLIENTE UNO", "", "TAREA A", "PLANTA", "1", "2", "2", "10", ""],
    ], ";")

    [fila] = leer_planilla(ruta)

    assert fila.fecha_a_facturar == "1/9/2025"


# ─── UM a unidad ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("PLANTA", "plantas"),
    ("TANCADA", "tancadas"),
    ("HORAS TRACTOR", "horas_tractor"),
    ("HORAS PEON", "horas_peon"),
    ("HECTAREA", "hectareas"),
    ("BINS", "bins"),
    ("BINS C", "bins_c"),
    ("BINS M", "bins_m"),
    ("VIAJES", "viajes"),
    # Sin acentos, en mayúsculas y con los espacios colapsados.
    ("Horas Peón", "horas_peon"),
    ("  horas   tractor ", "horas_tractor"),
    ("HECTÁREA", "hectareas"),
    ("bins\tc", "bins_c"),
])
def test_leer_unidad_traduce_la_tabla_de_um(texto, esperado):
    assert leer_unidad(texto) == esperado


@pytest.mark.parametrize("texto", [
    "NO FACTURABLE",
    "no  facturable",
    "",
    "   ",
    None,
    "PLANTAS",
    "HORA PEON",
    "KG",
])
def test_leer_unidad_no_traduce_no_facturable_vacia_ni_otra(texto):
    # Su Comprobante se omite y se lista (pregunta 2): eso es de C3.
    assert leer_unidad(texto) is None


# ─── Número del Comprobante ─────────────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("123", "123"),
    ("  0001234 ", "0001234"),
    # Compuestos, tal cual con la normalización de la regla 1 (pregunta 3).
    ("10-11", "10-11"),
    ("10 - 11", "10 - 11"),
    ("  10   -  11 ", "10 - 11"),
    ("F.10 - NC 11", "F.10 - NC 11"),
    ("f.10 - nc 11", "F.10 - NC 11"),
    # Cualquier otro texto también se migra tal cual.
    ("a confirmar", "A CONFIRMAR"),
    ("--", "--"),
])
def test_leer_numero_comprobante_normaliza_como_la_regla_1(texto, esperado):
    assert leer_numero_comprobante(texto) == esperado


@pytest.mark.parametrize("texto", ["", "   ", None, "-", " - "])
def test_leer_numero_comprobante_vacio_o_guion_es_sin_numero(texto):
    assert leer_numero_comprobante(texto) is None


def test_leer_numero_comprobante_con_barra_es_ilegible():
    # La barra separa las partes de clave_identidad.
    with pytest.raises(ValorIlegible):
        leer_numero_comprobante("10 | 11")


def test_leer_numero_comprobante_de_mas_de_30_caracteres_no_se_migra():
    assert leer_numero_comprobante("1" * 30) == "1" * 30
    # Se mide ya normalizado: los espacios colapsados no cuentan.
    assert leer_numero_comprobante("F.1" + " " * 40 + "NC 2") == "F.1 NC 2"
    with pytest.raises(NumeroDemasiadoLargo):
        leer_numero_comprobante("1" * 31)


def test_numero_demasiado_largo_no_es_ilegible():
    # Son dos motivos distintos en el listado de omitidos.
    assert not issubclass(NumeroDemasiadoLargo, ValorIlegible)
