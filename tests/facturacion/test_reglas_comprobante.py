"""Reglas puras del Comprobante (plan de la E2, sección 3.1, reglas 1, 3 y 5).

Lo que cuidan estos tests:
- que dos formas de escribir el mismo número den la misma clave, porque de eso
  depende el 409 de repetido y el "sin duplicar" de la migración del histórico;
- que el importe se redondee igual que en el front (los casos fijos de A1 se
  repiten en src/modulos/facturacion/numeros.test.js): si difieren, la pantalla
  muestra un total y la base guarda otro;
- que una Nota de crédito reste.

Datos inventados.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.modulos.facturacion.services.reglas_comprobante import (
    FACTURA,
    NOTA_CREDITO,
    TIPOS,
    NumeroInvalido,
    calcular_importe,
    clave_identidad,
    normalizar_empresa,
    normalizar_numero,
    total_firmado,
)


# ─── Regla 1: normalización ─────────────────────────────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    ("0001-00012345", "0001-00012345"),
    ("  0001-00012345  ", "0001-00012345"),
    ("a 0001   123", "A 0001 123"),
    ("f.10 - nc 11", "F.10 - NC 11"),
    ("\t12\n 34 ", "12 34"),
])
def test_normalizar_numero_recorta_colapsa_y_pasa_a_mayusculas(texto, esperado):
    assert normalizar_numero(texto) == esperado


def test_normalizar_numero_no_toca_los_ceros():
    # Pregunta 11: texto libre, copiado tal cual figura en el PDF.
    assert normalizar_numero("00012") == "00012"


@pytest.mark.parametrize("texto", ["", "   ", "\t\n", None])
def test_normalizar_numero_rechaza_vacio(texto):
    with pytest.raises(NumeroInvalido):
        normalizar_numero(texto)


@pytest.mark.parametrize("texto", ["12|34", "|", " 12 | "])
def test_normalizar_numero_rechaza_la_barra(texto):
    # La barra separa las partes de clave_identidad.
    with pytest.raises(NumeroInvalido):
        normalizar_numero(texto)


def test_normalizar_numero_es_idempotente():
    una_vez = normalizar_numero("  a  12 ")
    assert normalizar_numero(una_vez) == una_vez


@pytest.mark.parametrize("texto, esperado", [
    ("Empresa Uno SA", "EMPRESA UNO SA"),
    ("  empresa uno sa  ", "EMPRESA UNO SA"),
    ("EMPRESA DOS", "EMPRESA DOS"),
])
def test_normalizar_empresa_recorta_y_pasa_a_mayusculas(texto, esperado):
    assert normalizar_empresa(texto) == esperado


# ─── clave_identidad, en sus tres formas ────────────────────────────────────

def test_clave_de_un_comprobante_cargado_a_mano():
    # Con el tipo tal cual (R3): Facturas y Notas de crédito numeran aparte.
    assert clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="factura", numero="0001-123",
    ) == "E|EMPRESA UNO|factura|0001-123"
    assert clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="nota_credito", numero="0001-123",
    ) == "E|EMPRESA UNO|nota_credito|0001-123"


def test_clave_E_separa_la_factura_de_la_nota_con_el_mismo_numero():
    assert clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="factura", numero="5",
    ) != clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="nota_credito", numero="5",
    )


@pytest.mark.parametrize("tipo", [None, "", "remito", "Factura"])
def test_clave_E_con_un_tipo_desconocido_no_se_arma(tipo):
    with pytest.raises(ValueError):
        clave_identidad(historico=False, empresa="Empresa Uno", tipo=tipo, numero="5")


def test_clave_E_iguala_espacios_y_minusculas():
    # A4: "repetido con espacios o minúsculas distintas" se apoya en esto.
    assert clave_identidad(
        historico=False, empresa="  empresa uno ", tipo="factura",
        numero=" a  0001-123 ",
    ) == clave_identidad(
        historico=False, empresa="EMPRESA UNO", tipo="factura", numero="A 0001-123",
    )


def test_clave_E_no_depende_del_cliente():
    # El número es único por Empresa emisora, no por Cliente.
    assert clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="factura", numero="5",
        cliente_id=1,
    ) == clave_identidad(
        historico=False, empresa="Empresa Uno", tipo="factura", numero="5",
        cliente_id=2,
    )


def test_clave_de_un_historico_con_numero():
    assert clave_identidad(
        historico=True, cliente_id=12, numero=" f.10 - nc 11 ",
    ) == "H|12|F.10 - NC 11"


def test_clave_H_separa_el_mismo_numero_en_dos_clientes():
    # En la planilla el mismo número aparece para dos Clientes.
    assert clave_identidad(historico=True, cliente_id=1, numero="100") != (
        clave_identidad(historico=True, cliente_id=2, numero="100")
    )


def test_clave_de_un_historico_sin_numero():
    assert clave_identidad(
        historico=True, cliente_id=12, fecha_a_facturar=date(2025, 9, 1),
    ) == "S|12|2025-09-01"


def test_clave_S_separa_por_fecha_a_facturar():
    assert clave_identidad(
        historico=True, cliente_id=12, fecha_a_facturar=date(2025, 9, 1),
    ) != clave_identidad(
        historico=True, cliente_id=12, fecha_a_facturar=date(2025, 9, 16),
    )


def test_las_tres_formas_no_se_pisan():
    claves = {
        clave_identidad(historico=False, empresa="12", tipo="factura", numero="100"),
        clave_identidad(historico=True, cliente_id=12, numero="100"),
        clave_identidad(
            historico=True, cliente_id=12, fecha_a_facturar=date(2025, 9, 1),
        ),
    }
    assert len(claves) == 3


def test_clave_E_rechaza_numero_invalido():
    with pytest.raises(NumeroInvalido):
        clave_identidad(historico=False, empresa="Empresa Uno", tipo="factura",
                        numero="1|2")
    with pytest.raises(NumeroInvalido):
        clave_identidad(historico=False, empresa="Empresa Uno", tipo="factura",
                        numero="  ")


def test_clave_E_sin_empresa_no_se_arma():
    with pytest.raises(ValueError):
        clave_identidad(historico=False, empresa="  ", tipo="factura", numero="100")


def test_clave_H_rechaza_numero_con_barra():
    with pytest.raises(NumeroInvalido):
        clave_identidad(historico=True, cliente_id=12, numero="1|2")


@pytest.mark.parametrize("argumentos", [
    {"numero": "100"},                                 # sin cliente
    {"fecha_a_facturar": date(2025, 9, 1)},            # sin cliente
    {"cliente_id": 12},                                # ni número ni fecha
])
def test_clave_de_historico_incompleta_no_se_arma(argumentos):
    with pytest.raises(ValueError):
        clave_identidad(historico=True, **argumentos)


def test_las_claves_entran_en_la_columna():
    # clave_identidad es VARCHAR(160); empresa hasta 100, el tipo más largo
    # (nota_credito) 12 y número hasta 30.
    clave = clave_identidad(historico=False, empresa="E" * 100,
                            tipo="nota_credito", numero="9" * 30)
    assert len(clave) <= 160


# ─── Regla 3: importe ───────────────────────────────────────────────────────

# Los mismos casos fijos que el front (FA1, importeDeLinea).
@pytest.mark.parametrize("cantidad, precio, importe", [
    ("3", "0.005", "0.02"),
    ("1.5", "2.3333", "3.50"),
    ("56710", "313.56", "17781987.60"),
])
def test_calcular_importe_casos_fijos(cantidad, precio, importe):
    resultado = calcular_importe(Decimal(cantidad), Decimal(precio))
    assert resultado == Decimal(importe)
    # Siempre con dos decimales: el texto del JSON es el mismo que el del front.
    assert str(resultado) == importe


def test_calcular_importe_redondea_la_mitad_hacia_arriba():
    # 0.125 con ROUND_HALF_EVEN daría 0.12.
    assert calcular_importe(Decimal("1"), Decimal("0.125")) == Decimal("0.13")


def test_calcular_importe_acepta_texto_y_enteros():
    assert calcular_importe("1.5", "2.3333") == Decimal("3.50")
    assert calcular_importe(3, "0.005") == Decimal("0.02")


def test_calcular_importe_con_precio_cero():
    assert str(calcular_importe(Decimal("10"), Decimal("0"))) == "0.00"


# ─── Regla 5: total con signo ───────────────────────────────────────────────

def test_tipos():
    assert FACTURA == "factura"
    assert NOTA_CREDITO == "nota_credito"
    assert TIPOS == (FACTURA, NOTA_CREDITO)


def test_total_de_una_factura_es_positivo():
    assert total_firmado(
        FACTURA, [Decimal("0.02"), Decimal("3.50"), Decimal("17781987.60")],
    ) == Decimal("17781991.12")


def test_total_de_una_nota_de_credito_es_negativo():
    assert total_firmado(
        NOTA_CREDITO, [Decimal("0.02"), Decimal("3.50")],
    ) == Decimal("-3.52")


def test_total_sin_lineas_es_cero_sin_signo():
    assert str(total_firmado(FACTURA, [])) == "0.00"
    assert str(total_firmado(NOTA_CREDITO, [])) == "0.00"


def test_total_de_un_tipo_desconocido_no_se_calcula():
    with pytest.raises(ValueError):
        total_firmado("nota_debito", [Decimal("1.00")])
