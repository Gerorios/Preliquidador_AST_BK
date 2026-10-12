"""La lectura del maestro de tareas del sistema de campo (plan de la E1, D6, y
docs/superpowers/plans/2026-10-12-unidad-desde-campo.md, B2).

El SQL es de MySQL y no corre en SQLite: acá se prueba lo que el módulo pone y
saca de la base —qué columnas pide, qué filtra, cómo arma cada tarea con su
grupo y su Unidad sugerida— y que un
corte del campo llegue como ExternaNoDisponible, que main.py convierte en 503.
"""
import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.core.database import ExternaNoDisponible
from app.modulos.facturacion.services.consulta_externa import (
    QUERY_TAREAS,
    ConsultaExternaService,
    normalizar_nombre,
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


# ─── Las tareas ─────────────────────────────────────────────────────────────

COLUMNAS = ("tarea_id", "nombre_tarea", "descripcion")


def test_obtener_tareas_arma_cada_tarea_en_el_orden_en_que_llegan():
    externa = SesionFalsa(
        columnas=COLUMNAS,
        filas=[(12, "TAREA B", "GRUPO 1;PAGO;HORAS PEON"), (5, "TAREA A", None),
               (40, "TAREA C", "GRUPO 2;PAGO;NO FACTURABLE")],
    )
    tareas = ConsultaExternaService(externa).obtener_tareas()

    # Sólo los valores traducidos: ni el texto crudo ni un sin_definir aparte.
    assert tareas == [
        {"tarea_id": 12, "nombre": "TAREA B", "grupo_tarea": "GRUPO 1",
         "unidad_sugerida": "horas_peon", "no_facturable": False},
        {"tarea_id": 5, "nombre": "TAREA A", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False},
        {"tarea_id": 40, "nombre": "TAREA C", "grupo_tarea": "GRUPO 2",
         "unidad_sugerida": None, "no_facturable": True},
    ]
    query, _ = externa.llamadas[0]
    assert query is QUERY_TAREAS


# Sin definir es (None, False); No facturable es (None, True).
@pytest.mark.parametrize("descripcion, grupo, unidad, no_facturable", [
    ("G;P;PLANTA;EXTRA", "G", "plantas", False),
    ("G;P;PLANTA", "G", "plantas", False),
    # Con dos segmentos el segundo es el grupo de pago, no la unidad: es el
    # caso que SUBSTRING_INDEX en SQL leería mal.
    ("G;HORAS PEON", "G", None, False),
    ("G", "G", None, False),
    ("", None, None, False),
    (None, None, None, False),
    ("G;P;", "G", None, False),
    (" G ; P ; horas  tractor ", "G", "horas_tractor", False),
    ("G;P;NO FACTURABLE", "G", None, True),
    (";P;BINS C", None, "bins_c", False),
])
def test_el_grupo_y_la_unidad_salen_de_la_descripcion(descripcion, grupo, unidad, no_facturable):
    externa = SesionFalsa(columnas=COLUMNAS, filas=[(1, "TAREA", descripcion)])
    (tarea,) = ConsultaExternaService(externa).obtener_tareas()

    assert tarea["grupo_tarea"] == grupo
    assert tarea["unidad_sugerida"] == unidad
    assert tarea["no_facturable"] is no_facturable


def test_el_sql_trae_la_descripcion_cruda_y_filtra_las_bajas():
    sql = " ".join(str(QUERY_TAREAS).split())
    assert "ta.id AS tarea_id" in sql
    assert "ta.nombre AS nombre_tarea" in sql
    # La descripción viene cruda: el corte en segmentos se hace en Python.
    assert "ta.descripcion" in sql
    assert "SUBSTRING_INDEX" not in sql
    assert "WHERE ta.estado <> 9" in sql
    assert "ORDER BY ta.nombre" in sql
    # Ni el grupo de pago ni el grupo_factura: no los usa el módulo.
    assert "grupo_pago" not in sql
    assert "grupo_factura" not in sql


# ─── El campo caído ─────────────────────────────────────────────────────────

class SesionQueCorta:
    def execute(self, *a, **k):
        # Lo que levanta pymysql cuando vence read_timeout: 2013 Lost connection.
        raise OperationalError("SELECT ...", {}, pymysql.err.OperationalError(
            2013, "Lost connection to MySQL server during query"))


class SesionQueRechazaAcceso:
    def execute(self, *a, **k):
        # Lo que levanta pymysql si el campo cambia o bloquea las credenciales.
        raise OperationalError("SELECT ...", {}, pymysql.err.OperationalError(
            1045, "Access denied for user 'x'@'y' (using password: YES)"))


class SesionQueCortaSinCodigo:
    def execute(self, *a, **k):
        raise OperationalError("SELECT ...", {}, Exception())


def test_un_corte_da_externa_no_disponible_con_no_respondio():
    with pytest.raises(ExternaNoDisponible) as exc:
        ConsultaExternaService(SesionQueCorta()).obtener_tareas()
    assert "no respondió" in str(exc.value)


def test_acceso_rechazado_da_externa_no_disponible_sin_pedir_reintentar():
    with pytest.raises(ExternaNoDisponible) as exc:
        ConsultaExternaService(SesionQueRechazaAcceso()).obtener_tareas()
    assert "rechazó el acceso" in str(exc.value)
    assert "Reintentá" not in str(exc.value)


def test_un_error_sin_codigo_sigue_siendo_externa_no_disponible():
    # Un orig sin args no puede romper la traducción con un IndexError (500).
    with pytest.raises(ExternaNoDisponible) as exc:
        ConsultaExternaService(SesionQueCortaSinCodigo()).obtener_tareas()
    assert "no respondió" in str(exc.value)


# ─── El nombre normalizado ──────────────────────────────────────────────────

def test_normalizar_nombre_recorta_colapsa_espacios_y_pasa_a_mayusculas():
    assert normalizar_nombre("  tarea   uno ") == "TAREA UNO"


def test_normalizar_nombre_de_none_es_vacio():
    assert normalizar_nombre(None) == ""


def test_normalizar_nombre_no_aplica_alias():
    # tarea_canonica de Preliquidación cambia este alias de pago por su
    # canónica (ADR-0012). Acá no: la Unidad sugerida es de cada tarea del
    # campo, no de cómo se le paga a quien la hizo.
    alias = "Mantenimientos mecanicos  horas guardia (talleres)"
    assert normalizar_nombre(alias) == "MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)"
