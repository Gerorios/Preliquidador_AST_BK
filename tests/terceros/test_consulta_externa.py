"""Las tres consultas del módulo que salen de una base (etapa 1).

El SQL es de MySQL (DATE_FORMAT, ROW_NUMBER, ISNULL) y no corre en SQLite, así
que acá no se prueba qué devuelve la base: se prueba lo que el módulo pone y
saca de ella —el rango de fechas de la quincena, la base a la que va cada
consulta y las columnas del contrato—, que es donde se rompen las cosas en
silencio. Que los números coincidan con el Excel se comprueba contra las bases
reales con scripts/validar_terceros_etapa1.py.
"""
from datetime import date

import pytest

from app.modulos.terceros.services.consulta_externa import (
    COLUMNAS_CARGAS_COMBUSTIBLE,
    COLUMNAS_REPUESTOS,
    COLUMNAS_VIAJES,
    QUERY_CARGAS_COMBUSTIBLE,
    QUERY_REPUESTOS,
    QUERY_VIAJES,
    ConsultaExternaService,
)


class ResultadoFalso:
    def __init__(self, columnas, filas):
        self._columnas, self._filas = columnas, filas

    def keys(self):
        return list(self._columnas)

    def fetchall(self):
        return list(self._filas)


class SesionFalsa:
    """Anota con qué la llamaron y devuelve las filas que se le pasaron."""

    def __init__(self, columnas=(), filas=()):
        self.columnas, self.filas = columnas, filas
        self.llamadas = []

    def execute(self, query, params=None):
        self.llamadas.append((query, params))
        return ResultadoFalso(self.columnas, self.filas)


def _servicio(externa=None, sueldos=None):
    return ConsultaExternaService(externa or SesionFalsa(), sueldos or SesionFalsa())


# ─── El rango de fechas de la quincena ──────────────────────────────────────

@pytest.mark.parametrize("metodo", ["viajes", "cargas_combustible"])
def test_primera_quincena_va_del_1_al_15(metodo):
    externa = SesionFalsa()
    getattr(_servicio(externa=externa), metodo)(date(2026, 8, 1))
    _, params = externa.llamadas[0]
    assert params == {"fecha_desde": date(2026, 8, 1), "fecha_hasta": date(2026, 8, 15)}


@pytest.mark.parametrize("metodo", ["viajes", "cargas_combustible"])
def test_segunda_quincena_va_del_16_a_fin_de_mes(metodo):
    externa = SesionFalsa()
    getattr(_servicio(externa=externa), metodo)(date(2026, 8, 16))
    _, params = externa.llamadas[0]
    assert params == {"fecha_desde": date(2026, 8, 16), "fecha_hasta": date(2026, 8, 31)}


def test_la_segunda_de_febrero_termina_el_28_o_el_29():
    externa = SesionFalsa()
    _servicio(externa=externa).viajes(date(2027, 2, 16))
    assert externa.llamadas[0][1]["fecha_hasta"] == date(2027, 2, 28)
    externa = SesionFalsa()
    _servicio(externa=externa).viajes(date(2028, 2, 16))
    assert externa.llamadas[0][1]["fecha_hasta"] == date(2028, 2, 29)


def test_repuestos_tambien_se_acota_a_la_quincena():
    sueldos = SesionFalsa()
    _servicio(sueldos=sueldos).repuestos(date(2026, 8, 1))
    _, params = sueldos.llamadas[0]
    assert params == {"fecha_desde": date(2026, 8, 1), "fecha_hasta": date(2026, 8, 15)}


# ─── Cada consulta a su base ────────────────────────────────────────────────

def test_viajes_y_combustible_van_al_sistema_de_campo():
    externa, sueldos = SesionFalsa(), SesionFalsa()
    servicio = ConsultaExternaService(externa, sueldos)
    servicio.viajes(date(2026, 8, 1))
    servicio.cargas_combustible(date(2026, 8, 1))
    assert [q for q, _ in externa.llamadas] == [QUERY_VIAJES, QUERY_CARGAS_COMBUSTIBLE]
    assert sueldos.llamadas == []


def test_repuestos_va_al_sistema_de_compras():
    externa, sueldos = SesionFalsa(), SesionFalsa()
    ConsultaExternaService(externa, sueldos).repuestos(date(2026, 8, 1))
    assert [q for q, _ in sueldos.llamadas] == [QUERY_REPUESTOS]
    assert externa.llamadas == []


# ─── El contrato de columnas ────────────────────────────────────────────────

@pytest.mark.parametrize("query,columnas", [
    (QUERY_VIAJES, COLUMNAS_VIAJES),
    (QUERY_CARGAS_COMBUSTIBLE, COLUMNAS_CARGAS_COMBUSTIBLE),
    (QUERY_REPUESTOS, COLUMNAS_REPUESTOS),
])
def test_el_sql_declara_las_columnas_del_contrato(query, columnas):
    sql = str(query)
    for columna in columnas:
        assert columna in sql, f"falta {columna} en el SELECT"


@pytest.mark.parametrize("query", [QUERY_VIAJES, QUERY_CARGAS_COMBUSTIBLE, QUERY_REPUESTOS])
def test_las_fechas_son_parametros_y_no_estan_pegadas_en_el_sql(query):
    sql = str(query)
    assert ":fecha_desde" in sql and ":fecha_hasta" in sql
    assert "CURDATE()" not in sql, "quedó el filtro por año en curso del original"


def test_las_filas_se_devuelven_como_diccionarios_por_nombre_de_columna():
    externa = SesionFalsa(
        columnas=COLUMNAS_VIAJES,
        filas=[tuple(range(len(COLUMNAS_VIAJES)))],
    )
    filas = _servicio(externa=externa).viajes(date(2026, 8, 1))
    assert filas == [dict(zip(COLUMNAS_VIAJES, range(len(COLUMNAS_VIAJES))))]


def test_repuestos_trae_las_dos_fechas():
    """La del encabezado del movimiento y la de la descarga a la maquinaria.
    Las dos, porque hoy se imputa por la primera y la correcta es la segunda
    (plan-terceros.md, sección 3): sin las dos no se puede medir el desvío."""
    assert "fecha" in COLUMNAS_REPUESTOS
    assert "fecha_descarga" in COLUMNAS_REPUESTOS
    sql = str(QUERY_REPUESTOS)
    assert "pp.fechamovim AS fecha_descarga" in sql
    assert "AND ru.fecha BETWEEN :fecha_desde AND :fecha_hasta" in sql


def test_los_viajes_dejan_afuera_las_planillas_sin_colectivo():
    """Sin colectivo no hay tercero a quien pagarle."""
    assert "NOT LIKE 'SIN COLECTIVO" in str(QUERY_VIAJES)


def test_los_repuestos_son_solo_de_maquinaria_de_terceros():
    assert "LIKE '%%TERCERO%%'" in str(QUERY_REPUESTOS)


def test_una_reparacion_cobra_su_importe_y_un_insumo_cantidad_por_precio():
    """En la rama de reparaciones cantcargas viene en 0: calcularla como
    cantidad x precio daba $0 en todas (eran 50 registros de hasta $586.776)."""
    sql = str(QUERY_REPUESTOS)
    assert "CASE WHEN ru.reparacion = 'S' THEN ru.detalle_importe" in sql
    assert "ELSE ru.ingreso * ru.precargas END AS monto_total" in sql


def test_el_precio_del_insumo_sale_de_la_factura_vigente_a_la_descarga():
    """Sin el as-of join, el 90% de las líneas de 2026 tomaba una factura
    cualquiera entre varias con precios distintos."""
    sql = str(QUERY_REPUESTOS)
    assert "ROW_NUMBER() OVER (" in sql
    assert "WHERE rn_factura = 1" in sql
