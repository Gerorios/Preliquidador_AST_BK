"""
Tests del cache a nivel de proceso de SueldosService.

Verifican que las ~15.500 filas de nuempleados se cargan UNA sola vez por
proceso (dentro del TTL) y se reusan entre instancias/requests, y que
refrescar_cache_sueldos() fuerza una recarga.

Usan un fake de db (NO la BD real db_sueldos).
"""
import pytest

from app.services import sueldos_service
from app.services.sueldos_service import SueldosService, refrescar_cache_sueldos


# Filas fijas con el shape que espera _cargar_cache:
# (empresa, legajo, apellido_nombre, cuil, categoria, seccion, cargo, jornal)
FILAS = [
    ("LA ASTURIANA", "111", "PEREZ JUAN", "20111111111", "A", "SEC1", "CARGO1", "J1"),
    ("PAMPLONA", "999", "PEREZ JUAN", "20111111111", "B", "SEC2", "CARGO2", "J2"),
    ("LA ASTURIANA", "222", "GOMEZ ANA", "20222222222", "C", "SEC3", "CARGO3", "J3"),
]


class _FakeResult:
    def __init__(self, filas):
        self._filas = filas

    def fetchall(self):
        return self._filas


class _FakeDB:
    """db falso que cuenta cuántas veces se ejecuta la query."""
    def __init__(self, filas):
        self._filas = filas
        self.execute_count = 0

    def execute(self, *_args, **_kwargs):
        self.execute_count += 1
        return _FakeResult(self._filas)


@pytest.fixture(autouse=True)
def _reset_store():
    # Resetea el store de módulo para que el test no dependa del orden.
    refrescar_cache_sueldos()
    yield
    refrescar_cache_sueldos()


def test_cache_de_proceso_se_reusa_entre_instancias():
    db1 = _FakeDB(FILAS)
    db2 = _FakeDB(FILAS)

    # Primera instancia: carga desde la "BD" (1 query).
    s1 = SueldosService(db1)
    assert s1.resolver_empresa_por_legajo("222") == ("LA ASTURIANA", False)
    assert db1.execute_count == 1

    # Segunda instancia (nuevo request): reusa el cache de proceso, NO consulta.
    s2 = SueldosService(db2)
    assert s2.resolver_empresa_por_legajo("222") == ("LA ASTURIANA", False)
    assert db2.execute_count == 0

    # El total de queries a la BD sigue siendo UNA sola.
    assert db1.execute_count + db2.execute_count == 1


def test_refrescar_cache_fuerza_segunda_carga():
    db1 = _FakeDB(FILAS)
    s1 = SueldosService(db1)
    s1._cargar_cache()
    assert db1.execute_count == 1

    # Sin refrescar, otra instancia no consulta.
    db2 = _FakeDB(FILAS)
    s2 = SueldosService(db2)
    s2._cargar_cache()
    assert db2.execute_count == 0

    # Tras refrescar, la próxima carga vuelve a consultar la BD.
    refrescar_cache_sueldos()
    db3 = _FakeDB(FILAS)
    s3 = SueldosService(db3)
    s3._cargar_cache()
    assert db3.execute_count == 1


def test_cache_expira_por_ttl(monkeypatch):
    from datetime import datetime, timedelta

    db1 = _FakeDB(FILAS)
    SueldosService(db1)._cargar_cache()
    assert db1.execute_count == 1

    # Simular que la carga fue hace más que el TTL → debe recargar.
    vencido = datetime.now() - sueldos_service._TTL_CACHE - timedelta(seconds=1)
    sueldos_service._STORE["cargado_en"] = vencido

    db2 = _FakeDB(FILAS)
    SueldosService(db2)._cargar_cache()
    assert db2.execute_count == 1
