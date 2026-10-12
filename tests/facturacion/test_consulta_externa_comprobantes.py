"""Las lecturas del campo y de sueldos que usan los Comprobantes (plan de la
E2, sección 3.1, regla 8, y paso A3).

El SQL es de MySQL y no corre en SQLite: acá se prueba lo que el módulo pone y
saca de la base —qué filtra cada consulta, a qué base va, cómo arma cada fila—
y la caché de proceso de 10 minutos, con el reloj del módulo cambiado a mano.
Datos inventados.
"""
import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.core.database import ExternaNoDisponible
from app.modulos.facturacion.services import consulta_externa
from app.modulos.facturacion.services.consulta_externa import (
    QUERY_CLIENTES,
    QUERY_CLIENTES_CON_BAJA,
    QUERY_EMPRESAS,
    QUERY_FINCAS_DE_CLIENTE,
    QUERY_TAREAS,
    QUERY_TAREAS_CON_BAJA,
    QUERY_TODAS_LAS_FINCAS,
    ConsultaExternaService,
    invalidar_cache,
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


class SesionQueCorta:
    def execute(self, *a, **k):
        raise OperationalError("SELECT ...", {}, pymysql.err.OperationalError(
            2013, "Lost connection to MySQL server during query"))


class Reloj:
    """Reemplaza el reloj del módulo: avanza sólo cuando el test lo pide."""

    def __init__(self, ahora=1000.0):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


@pytest.fixture(autouse=True)
def cache_limpia():
    invalidar_cache()
    yield
    invalidar_cache()


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(consulta_externa, "_reloj", r)
    return r


def _sql(query) -> str:
    return " ".join(str(query).split())


# ─── Clientes ───────────────────────────────────────────────────────────────

def test_clientes_devuelve_id_nombre_y_activo_de_los_activos():
    externa = SesionFalsa(filas=[(3, "CLIENTE DOS"), (1, "CLIENTE UNO")])
    clientes = ConsultaExternaService(externa).clientes()

    assert clientes == [
        {"id": 3, "nombre": "CLIENTE DOS", "activo": True},
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True},
    ]
    query, _ = externa.llamadas[0]
    assert query is QUERY_CLIENTES


def test_el_sql_de_clientes_filtra_las_bajas_y_trae_el_id():
    sql = _sql(QUERY_CLIENTES)
    assert "c.id" in sql and "c.nombre" in sql
    assert "WHERE c.estado <> 9" in sql
    assert "ORDER BY c.nombre" in sql


def test_clientes_con_baja_trae_tambien_los_de_baja_marcados_inactivos():
    externa = SesionFalsa(filas=[(1, "CLIENTE UNO", 1), (2, "CLIENTE BAJA", 0)])
    clientes = ConsultaExternaService(externa).clientes(incluir_baja=True)

    assert clientes == [
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True},
        {"id": 2, "nombre": "CLIENTE BAJA", "activo": False},
    ]
    query, _ = externa.llamadas[0]
    assert query is QUERY_CLIENTES_CON_BAJA


def test_el_sql_de_clientes_con_baja_no_filtra_y_marca_la_baja_igual():
    sql = _sql(QUERY_CLIENTES_CON_BAJA)
    assert "WHERE" not in sql
    # Activo con la misma regla que el filtro: estado distinto de 9 (un NULL,
    # como en el WHERE, no cuenta como activo).
    assert "CASE WHEN c.estado <> 9 THEN 1 ELSE 0 END AS activo" in sql
    assert "ORDER BY c.nombre" in sql


# ─── Fincas ─────────────────────────────────────────────────────────────────

def test_fincas_de_cliente_pasa_el_id_y_devuelve_id_y_nombre():
    externa = SesionFalsa(filas=[(21, "FINCA A"), (22, "FINCA B")])
    fincas = ConsultaExternaService(externa).fincas_de_cliente(7)

    assert fincas == [{"id": 21, "nombre": "FINCA A"}, {"id": 22, "nombre": "FINCA B"}]
    query, params = externa.llamadas[0]
    assert query is QUERY_FINCAS_DE_CLIENTE
    assert params == {"cliente_id": 7}


def test_el_sql_de_fincas_de_cliente_filtra_por_id_y_las_bajas():
    sql = _sql(QUERY_FINCAS_DE_CLIENTE)
    assert "f.idcliente = :cliente_id" in sql
    assert "f.estado <> 9" in sql
    assert "ORDER BY f.nombre" in sql


def test_todas_las_fincas_trae_id_nombre_y_cliente():
    externa = SesionFalsa(filas=[(21, "FINCA A", 1), (30, "FINCA C", 2)])
    fincas = ConsultaExternaService(externa).todas_las_fincas()

    assert fincas == [
        {"id": 21, "nombre": "FINCA A", "cliente_id": 1},
        {"id": 30, "nombre": "FINCA C", "cliente_id": 2},
    ]
    query, _ = externa.llamadas[0]
    assert query is QUERY_TODAS_LAS_FINCAS
    sql = _sql(QUERY_TODAS_LAS_FINCAS)
    assert "f.idcliente AS cliente_id" in sql
    assert "f.estado <> 9" in sql


# ─── Empresas (base de sueldos) ─────────────────────────────────────────────

def test_empresas_va_a_sueldos_recorta_saca_vacios_y_ordena():
    externa = SesionFalsa()
    sueldos = SesionFalsa(filas=[(" EMPRESA B ",), (None,), ("",), ("   ",),
                                 ("EMPRESA A",), ("EMPRESA A ",)])
    empresas = ConsultaExternaService(externa, sueldos).empresas()

    assert empresas == ["EMPRESA A", "EMPRESA B"]
    assert externa.llamadas == []
    query, _ = sueldos.llamadas[0]
    assert query is QUERY_EMPRESAS


def test_el_sql_de_empresas_es_el_de_preliquidacion():
    assert _sql(QUERY_EMPRESAS) == (
        "SELECT DISTINCT empresa FROM nuempleados "
        "WHERE borrado IS NULL OR borrado <> 'S' "
        "ORDER BY empresa"
    )


def test_empresas_sin_sesion_de_sueldos_avisa():
    with pytest.raises(RuntimeError):
        ConsultaExternaService(SesionFalsa()).empresas()


# ─── La caché de 10 minutos ─────────────────────────────────────────────────

@pytest.mark.parametrize("llamar", [
    lambda s: s.clientes(),
    lambda s: s.fincas_de_cliente(7),
    lambda s: s.empresas(),
], ids=["clientes", "fincas_de_cliente", "empresas"])
def test_la_segunda_llamada_dentro_de_10_minutos_no_vuelve_a_consultar(reloj, llamar):
    externa = SesionFalsa(filas=[(1, "CLIENTE UNO")])
    sueldos = SesionFalsa(filas=[("EMPRESA A",)])

    primera = llamar(ConsultaExternaService(externa, sueldos))
    reloj.ahora += 599
    # Otra instancia, como en otro pedido: la caché es del proceso.
    segunda = llamar(ConsultaExternaService(externa, sueldos))

    assert segunda == primera
    assert len(externa.llamadas) + len(sueldos.llamadas) == 1


@pytest.mark.parametrize("llamar", [
    lambda s: s.clientes(),
    lambda s: s.fincas_de_cliente(7),
    lambda s: s.empresas(),
], ids=["clientes", "fincas_de_cliente", "empresas"])
def test_pasados_10_minutos_vuelve_a_consultar(reloj, llamar):
    externa = SesionFalsa(filas=[(1, "CLIENTE UNO")])
    sueldos = SesionFalsa(filas=[("EMPRESA A",)])

    llamar(ConsultaExternaService(externa, sueldos))
    reloj.ahora += 601
    llamar(ConsultaExternaService(externa, sueldos))

    assert len(externa.llamadas) + len(sueldos.llamadas) == 2


def test_la_cache_de_fincas_es_por_cliente(reloj):
    externa = SesionFalsa(filas=[(21, "FINCA A")])
    servicio = ConsultaExternaService(externa)

    servicio.fincas_de_cliente(7)
    servicio.fincas_de_cliente(8)
    servicio.fincas_de_cliente(7)

    assert [p for _, p in externa.llamadas] == [{"cliente_id": 7}, {"cliente_id": 8}]


class SesionPorConsulta(SesionFalsa):
    """Devuelve filas distintas según la consulta."""

    def __init__(self, filas_por_consulta):
        super().__init__()
        self.filas_por_consulta = filas_por_consulta

    def execute(self, query, params=None):
        self.llamadas.append((query, params))
        return ResultadoFalso((), self.filas_por_consulta[query])


def test_la_cache_de_clientes_separa_activos_y_con_baja(reloj):
    externa = SesionPorConsulta({
        QUERY_CLIENTES_CON_BAJA: [(1, "CLIENTE UNO", 1), (2, "CLIENTE BAJA", 0)],
        QUERY_CLIENTES: [(1, "CLIENTE UNO")],
    })
    servicio = ConsultaExternaService(externa)

    con_baja = servicio.clientes(incluir_baja=True)
    activos = servicio.clientes()

    assert [q for q, _ in externa.llamadas] == [QUERY_CLIENTES_CON_BAJA, QUERY_CLIENTES]
    assert len(con_baja) == 2 and activos == [
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True}]


def test_un_corte_no_queda_en_la_cache(reloj):
    with pytest.raises(ExternaNoDisponible):
        ConsultaExternaService(SesionQueCorta()).clientes()

    externa = SesionFalsa(filas=[(1, "CLIENTE UNO")])
    assert ConsultaExternaService(externa).clientes() == [
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True}]
    assert len(externa.llamadas) == 1


@pytest.mark.parametrize("llamar", [
    lambda s: s.clientes(),
    lambda s: s.clientes(incluir_baja=True),
    lambda s: s.fincas_de_cliente(7),
    lambda s: s.todas_las_fincas(),
    lambda s: s.empresas(),
    lambda s: s.obtener_tareas(incluir_baja=True),
], ids=["clientes", "clientes_con_baja", "fincas_de_cliente", "todas_las_fincas",
        "empresas", "tareas_con_baja"])
def test_cada_lectura_traduce_un_corte_a_externa_no_disponible(llamar):
    with pytest.raises(ExternaNoDisponible):
        llamar(ConsultaExternaService(SesionQueCorta(), SesionQueCorta()))


# ─── Tareas con bajas, para el histórico ────────────────────────────────────

def test_obtener_tareas_sin_parametro_sigue_sin_bajas():
    externa = SesionFalsa(filas=[(5, "TAREA A", "G;P;PLANTA")])
    tareas = ConsultaExternaService(externa).obtener_tareas()

    query, _ = externa.llamadas[0]
    assert query is QUERY_TAREAS
    assert tareas == [{"tarea_id": 5, "nombre": "TAREA A", "grupo_tarea": "G",
                       "unidad_sugerida": "plantas", "no_facturable": False}]


def test_obtener_tareas_con_baja_usa_la_consulta_sin_filtro_y_arma_igual():
    externa = SesionFalsa(filas=[(5, "TAREA A", "G;P;PLANTA"), (9, "TAREA BAJA", None)])
    tareas = ConsultaExternaService(externa).obtener_tareas(incluir_baja=True)

    query, _ = externa.llamadas[0]
    assert query is QUERY_TAREAS_CON_BAJA
    assert tareas == [
        {"tarea_id": 5, "nombre": "TAREA A", "grupo_tarea": "G",
         "unidad_sugerida": "plantas", "no_facturable": False},
        {"tarea_id": 9, "nombre": "TAREA BAJA", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
    ]


def test_el_sql_de_tareas_con_baja_es_el_mismo_sin_el_filtro():
    sql = _sql(QUERY_TAREAS_CON_BAJA)
    assert "WHERE" not in sql
    assert _sql(QUERY_TAREAS).replace("WHERE ta.estado <> 9 ", "") == sql
