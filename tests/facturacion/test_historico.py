"""Migración del histórico: lectura de la planilla y clasificación de sus
filas (plan de la E2, sección 3.1, "Migración del histórico", y pares C1 a C3
de la sección 3.9).

Lo que cuidan estos tests:
- que un número es-AR se lea igual venga como venga ("1.234,56", "$ 1.234,56",
  "1234"), porque la conciliación por Cliente y mes compara sumas al centavo;
- que lo que no es un número ("-", "#VALUE!", más decimales que la columna) se
  marque ilegible en vez de leerse como otra cosa: así su grupo se omite y se
  lista, y nunca se migra un importe adivinado;
- que el CSV se lea con BOM, CRLF y `;`, que es como lo puede dejar Excel;
- que un encabezado faltante frene con un error que lo nombre;
- que una Línea mala omita su Comprobante entero, con el motivo de esa Línea,
  así nunca queda un Comprobante a medias y la conciliación cuadra.

Datos inventados.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.modulos.facturacion.services import historico as h
from app.modulos.facturacion.services.historico import (
    ENCABEZADOS,
    SIN_NUMERO_FACTURADO_HASTA,
    FilaPlanilla,
    Maestros,
    NumeroDemasiadoLargo,
    PlanillaInvalida,
    ValorIlegible,
    clasificar,
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


# ─── Clasificación y agrupado ───────────────────────────────────────────────

DESDE = date(2025, 4, 1)

# Con la forma de ConsultaExternaService: clientes(incluir_baja=True),
# obtener_tareas(incluir_baja=True) y todas_las_fincas().
MAESTROS = Maestros(
    clientes=[
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True},
        {"id": 2, "nombre": "CLIENTE DOS", "activo": False},
        {"id": 3, "nombre": "CLIENTE REPETIDO", "activo": True},
        {"id": 4, "nombre": "Cliente  Repetido", "activo": False},
    ],
    tareas=[
        {"tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "G",
         "unidad_sugerida": "plantas", "no_facturable": False},
        {"tarea_id": 11, "nombre": "TAREA B", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
        {"tarea_id": 12, "nombre": "TAREA DOBLE", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
        {"tarea_id": 13, "nombre": "Tarea Doble", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
    ],
    fincas=[
        {"id": 100, "nombre": "FINCA X", "cliente_id": 1},
        {"id": 101, "nombre": "FINCA X", "cliente_id": 2},
    ],
)


def _fila(fila, **cambios):
    datos = dict(
        fila=fila, fecha_a_facturar="1/9/2025", cliente="CLIENTE UNO", finca="",
        tarea="TAREA A", um="PLANTA", cantidad="10", precio="2,5",
        importe="25", numero="10", fecha_factura="",
    )
    datos.update(cambios)
    return FilaPlanilla(**datos)


def _clasificar(*filas, desde=DESDE):
    return clasificar(list(filas), MAESTROS, desde=desde)


def test_agrupa_por_cliente_y_numero_en_el_orden_del_csv():
    resultado = _clasificar(
        _fila(2, numero="10"),
        _fila(3, numero="11", tarea="TAREA B"),
        _fila(4, numero=" 10 ", fecha_a_facturar="16/9/2025"),
    )

    assert resultado.omitidos == []
    assert [(g.cliente_id, g.numero) for g in resultado.grupos] == [(1, "10"), (1, "11")]
    diez = resultado.grupos[0]
    assert diez.cliente_nombre == "CLIENTE UNO"
    assert diez.pendiente_de_facturar is False
    assert [linea.fila for linea in diez.lineas] == [2, 4]
    assert [linea.fecha for linea in diez.lineas] == [date(2025, 9, 1), date(2025, 9, 16)]


def test_la_linea_copia_los_nombres_del_maestro_y_los_valores_de_la_planilla():
    [grupo] = _clasificar(
        _fila(2, cliente=" cliente   úno ", tarea="tárea  a", um="Planta",
              cantidad="1.000", precio="12,3456", importe="$ 12.345,60"),
    ).grupos

    assert grupo.cliente_id == 1
    assert grupo.cliente_nombre == "CLIENTE UNO"
    [linea] = grupo.lineas
    assert linea == h.LineaHistorica(
        fila=2, fecha=date(2025, 9, 1), tarea_id=10, tarea_nombre="TAREA A",
        unidad="plantas", finca_id=None, finca_nombre=None,
        cantidad=Decimal("1000"), precio_unitario=Decimal("12.3456"),
        importe=Decimal("12345.60"),
    )


def test_el_importe_es_el_de_la_planilla_sin_recalcular():
    [grupo] = _clasificar(_fila(2, cantidad="3", precio="100", importe="299,99")).grupos

    assert grupo.lineas[0].importe == Decimal("299.99")


def test_el_mismo_numero_con_dos_clientes_son_dos_comprobantes():
    resultado = _clasificar(
        _fila(2, numero="10", cliente="CLIENTE UNO"),
        _fila(3, numero="10", cliente="CLIENTE DOS"),
    )

    # CLIENTE DOS está de baja: el histórico lo resuelve igual.
    assert [(g.cliente_id, g.numero) for g in resultado.grupos] == [(1, "10"), (2, "10")]


def test_el_numero_compuesto_se_agrupa_ya_normalizado():
    resultado = _clasificar(
        _fila(2, numero="F.1 - nc 2"),
        _fila(3, numero="f.1  -  NC 2"),
    )

    [grupo] = resultado.grupos
    assert grupo.numero == "F.1 - NC 2"
    assert len(grupo.lineas) == 2


def test_sin_numero_se_agrupa_por_cliente_y_fecha_a_facturar():
    resultado = _clasificar(
        _fila(2, numero="", fecha_a_facturar="1/9/2025"),
        _fila(3, numero="-", fecha_a_facturar="01/09/2025"),
        _fila(4, numero="", fecha_a_facturar="16/9/2025"),
        _fila(5, numero="-", fecha_a_facturar="1/9/2025", cliente="CLIENTE DOS"),
    )

    assert resultado.omitidos == []
    assert [
        (g.cliente_id, g.numero, g.fecha_a_facturar, [li.fila for li in g.lineas])
        for g in resultado.grupos
    ] == [
        (1, None, date(2025, 9, 1), [2, 3]),
        (1, None, date(2025, 9, 16), [4]),
        (2, None, date(2025, 9, 1), [5]),
    ]


def test_sin_numero_hasta_el_corte_cuenta_como_facturado_y_despues_queda_pendiente():
    assert SIN_NUMERO_FACTURADO_HASTA == date(2026, 7, 31)

    resultado = _clasificar(
        _fila(2, numero="", fecha_a_facturar="31/7/2026"),
        _fila(3, numero="", fecha_a_facturar="1/8/2026"),
        # Con número, nunca queda pendiente.
        _fila(4, numero="10", fecha_a_facturar="1/8/2026"),
    )

    assert [(g.numero, g.pendiente_de_facturar) for g in resultado.grupos] == [
        (None, False), (None, True), ("10", False),
    ]


def test_sin_numero_y_sin_fecha_a_facturar_se_omite_y_se_lista():
    resultado = _clasificar(
        _fila(2, numero="", fecha_a_facturar=""),
        _fila(3, numero="10"),
    )

    assert [g.numero for g in resultado.grupos] == ["10"]
    [omitido] = resultado.omitidos
    assert omitido.motivo == h.SIN_NUMERO_SIN_FECHA
    assert [f.fila for f in omitido.filas] == [2]


def test_la_fecha_del_comprobante_es_la_unica_fecha_fac_del_grupo():
    resultado = _clasificar(
        _fila(2, numero="10", fecha_factura=""),
        _fila(3, numero="10", fecha_factura="5/9/25"),
        _fila(4, numero="10", fecha_factura="05/09/2025"),
        _fila(5, numero="11", fecha_factura=""),
    )

    assert [(g.numero, g.fecha) for g in resultado.grupos] == [
        ("10", date(2025, 9, 5)), ("11", None),
    ]


def test_dos_fechas_fac_distintas_en_el_grupo_lo_omiten():
    resultado = _clasificar(
        _fila(2, numero="10", fecha_factura="5/9/2025"),
        _fila(3, numero="10", fecha_factura="6/9/2025"),
        _fila(4, numero="11"),
    )

    assert [g.numero for g in resultado.grupos] == ["11"]
    [omitido] = resultado.omitidos
    assert omitido.motivo == h.FECHA_FACTURA_EN_CONFLICTO
    assert [f.fila for f in omitido.filas] == [2, 3]


@pytest.mark.parametrize("cambios, motivo", [
    ({"um": "NO FACTURABLE"}, h.UM_NO_TRADUCIBLE),
    ({"um": ""}, h.UM_NO_TRADUCIBLE),
    ({"um": "KG"}, h.UM_NO_TRADUCIBLE),
    ({"importe": "#VALUE!"}, h.IMPORTE_ILEGIBLE),
    ({"importe": ""}, h.IMPORTE_VACIO),
    ({"cantidad": "abc"}, h.CANTIDAD_ILEGIBLE),
    ({"cantidad": ""}, h.CANTIDAD_VACIA),
    ({"precio": "1,23456"}, h.PRECIO_ILEGIBLE),
    ({"precio": ""}, h.PRECIO_VACIO),
    ({"importe": "-25"}, h.VALOR_NEGATIVO),
    ({"cantidad": "-10"}, h.VALOR_NEGATIVO),
    ({"precio": "-2,5"}, h.VALOR_NEGATIVO),
    ({"tarea": "TAREA Z"}, h.TAREA_NO_ENCONTRADA),
    ({"tarea": "tarea doble"}, h.TAREA_AMBIGUA),
    ({"fecha_a_facturar": "x"}, h.FECHA_A_FACTURAR_ILEGIBLE),
    ({"fecha_a_facturar": ""}, h.FECHA_A_FACTURAR_VACIA),
    ({"fecha_factura": "31/2/2025"}, h.FECHA_FACTURA_ILEGIBLE),
])
def test_una_linea_mala_omite_su_comprobante_entero(cambios, motivo):
    resultado = _clasificar(
        _fila(2, numero="10"),
        _fila(3, numero="10", **cambios),
        _fila(4, numero="99"),
    )

    assert [g.numero for g in resultado.grupos] == ["99"]
    [omitido] = resultado.omitidos
    assert omitido.motivo == motivo
    assert omitido.fila_mala == 3
    assert [f.fila for f in omitido.filas] == [2, 3]


@pytest.mark.parametrize("cambios, motivo", [
    ({"cliente": "CLIENTE Z"}, h.CLIENTE_NO_ENCONTRADO),
    ({"cliente": "cliente repetido"}, h.CLIENTE_AMBIGUO),
    ({"numero": "1" * 31}, h.NUMERO_DEMASIADO_LARGO),
    ({"numero": "1 | 2"}, h.NUMERO_ILEGIBLE),
])
def test_un_cliente_o_un_numero_que_no_sirven_omiten_el_comprobante(cambios, motivo):
    resultado = _clasificar(
        _fila(2, **cambios),
        _fila(3, **cambios),
        _fila(4, numero="99"),
    )

    assert [g.numero for g in resultado.grupos] == ["99"]
    [omitido] = resultado.omitidos
    assert omitido.motivo == motivo
    assert [f.fila for f in omitido.filas] == [2, 3]


def test_el_motivo_es_el_de_la_primera_linea_mala():
    resultado = _clasificar(
        _fila(2, numero="10"),
        _fila(3, numero="10", um="KG"),
        _fila(4, numero="10", tarea="TAREA Z"),
    )

    [omitido] = resultado.omitidos
    assert omitido.motivo == h.UM_NO_TRADUCIBLE
    assert omitido.fila_mala == 3
    assert omitido.detalle == "KG"
    assert [f.fila for f in omitido.filas] == [2, 3, 4]


def test_los_nombres_no_resueltos_se_cuentan_por_nombre_distinto():
    resultado = _clasificar(
        _fila(2, numero="10", cliente="CLIENTE Z"),
        _fila(3, numero="11", cliente="cliente  z"),
        _fila(4, numero="12", tarea="TAREA Z"),
        # La UM la omite antes, pero la tarea igual se cuenta.
        _fila(5, numero="13", um="KG", tarea="Tarea Z"),
        _fila(6, numero="14", cliente="cliente repetido"),
    )

    assert resultado.no_resueltos == {
        (h.CLIENTE_NO_ENCONTRADO, "CLIENTE Z"): 2,
        (h.TAREA_NO_ENCONTRADA, "TAREA Z"): 2,
        (h.CLIENTE_AMBIGUO, "CLIENTE REPETIDO"): 1,
    }


def test_un_comprobante_con_una_linea_anterior_a_desde_se_omite():
    resultado = _clasificar(
        _fila(2, numero="10", fecha_a_facturar="16/3/2025"),
        _fila(3, numero="10", fecha_a_facturar="1/4/2025"),
        _fila(4, numero="11", fecha_a_facturar="1/4/2025"),
    )

    assert [g.numero for g in resultado.grupos] == ["11"]
    [omitido] = resultado.omitidos
    assert omitido.motivo == h.ANTERIOR_A_DESDE
    assert [f.fila for f in omitido.filas] == [2, 3]


def test_la_finca_del_cliente_se_resuelve_y_la_no_encontrada_da_aviso_sin_frenar():
    resultado = _clasificar(
        _fila(2, numero="10", finca="finca  x"),
        _fila(3, numero="10", finca="FINCA Y"),
        _fila(4, numero="10", finca=""),
        # FINCA X existe, pero de otro Cliente.
        _fila(5, numero="11", cliente="CLIENTE DOS", finca="FINCA X"),
        _fila(6, numero="12", cliente="CLIENTE DOS", finca="FINCA W"),
    )

    assert resultado.omitidos == []
    diez, once, doce = resultado.grupos
    assert [(li.finca_id, li.finca_nombre) for li in diez.lineas] == [
        (100, "FINCA X"), (None, None), (None, None),
    ]
    assert [(li.finca_id, li.finca_nombre) for li in once.lineas] == [(101, "FINCA X")]
    assert [(li.finca_id, li.finca_nombre) for li in doce.lineas] == [(None, None)]
    assert resultado.avisos == [
        h.Aviso(fila=3, motivo=h.FINCA_NO_ENCONTRADA, detalle="FINCA Y"),
        h.Aviso(fila=6, motivo=h.FINCA_NO_ENCONTRADA, detalle="FINCA W"),
    ]


def test_la_cantidad_cero_se_migra_tal_cual():
    [grupo] = _clasificar(_fila(2, cantidad="0", importe="0")).grupos

    assert grupo.lineas[0].cantidad == Decimal("0")
    assert grupo.lineas[0].importe == Decimal("0")
