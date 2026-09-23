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


def test_grupos_pago_tambien_traduce_el_corte():
    # /grupos-pago consultaba la externa con execute crudo y devolvía 500.
    with pytest.raises(ExternaNoDisponible):
        ConsultaExternaService(DbQueCorta()).obtener_grupos_pago()


class DbQueRechazaAcceso:
    def execute(self, *a, **k):
        # Lo que levanta pymysql si ADCP cambia o bloquea las credenciales.
        import pymysql
        raise OperationalError("SELECT ...", {}, pymysql.err.OperationalError(
            1045, "Access denied for user 'x'@'y' (using password: YES)"))


def test_acceso_rechazado_no_pide_reintentar():
    with pytest.raises(ExternaNoDisponible) as exc:
        ConsultaExternaService(DbQueRechazaAcceso()).obtener_clientes()
    assert "rechazó el acceso" in str(exc.value)
    assert "Reintentá" not in str(exc.value)


class DbQueCortaSinCodigo:
    def execute(self, *a, **k):
        raise OperationalError("SELECT ...", {}, Exception())


def test_error_sin_codigo_sigue_siendo_externa_no_disponible():
    # Un orig sin args no puede romper la traducción con un IndexError (500).
    with pytest.raises(ExternaNoDisponible):
        ConsultaExternaService(DbQueCortaSinCodigo()).obtener_clientes()
