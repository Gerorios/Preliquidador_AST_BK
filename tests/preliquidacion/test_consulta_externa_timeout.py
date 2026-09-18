"""La consulta a la base externa (ADCP) tiene tope de lectura y, si se corta,
avisa con una excepción propia y un mensaje para el usuario."""
import pytest
from sqlalchemy.exc import OperationalError

from app.core import database
from app.modulos.preliquidacion.services.consulta_externa import (
    ConsultaExternaService, ExternaNoDisponible,
)
from datetime import date


class DbQueCorta:
    def execute(self, *a, **k):
        # Lo que levanta pymysql cuando vence read_timeout: 2013 Lost connection.
        raise OperationalError("SELECT ...", {}, Exception(
            "(2013, 'Lost connection to MySQL server during query')"))


def test_operational_error_se_traduce_a_externa_no_disponible():
    svc = ConsultaExternaService(DbQueCorta())
    with pytest.raises(ExternaNoDisponible) as exc:
        svc.obtener_tareas_quincena(date(2026, 9, 1))
    assert "base de datos de campo" in str(exc.value)


def test_todas_las_consultas_del_servicio_traducen_el_corte():
    # generar() también pasa por obtener_tareas() (_construir_cache); precios y
    # gerencial usan clientes/fincas/legajos. Todas tienen que avisar igual.
    svc = ConsultaExternaService(DbQueCorta())
    for llamada in (svc.obtener_tareas, svc.obtener_clientes, svc.obtener_legajos,
                    lambda: svc.obtener_fincas("CLIENTE A")):
        with pytest.raises(ExternaNoDisponible):
            llamada()


def test_engine_externa_tiene_tope_de_lectura():
    args = database.CONNECT_ARGS_EXTERNA
    assert args["read_timeout"] == 60
    assert args["connect_timeout"] == 10
    # Solo la externa: la propia escribe y no se corta a mitad de un commit.
    assert "read_timeout" not in (database.engine_propia.dialect.create_connect_args(
        database.engine_propia.url)[1])
