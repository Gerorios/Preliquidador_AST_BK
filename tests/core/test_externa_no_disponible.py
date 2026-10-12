"""La traducción de un error del sistema de campo (ADCP) a ExternaNoDisponible.

Vive en el núcleo porque la usan dos módulos (Preliquidación y Facturación): un
corte o un timeout pide reintentar; un acceso rechazado, avisar a sistemas.
"""
import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.core.database import ExternaNoDisponible, traducir_errores_externa


def _error(*args):
    return OperationalError("SELECT ...", {}, pymysql.err.OperationalError(*args))


def test_un_corte_pide_reintentar():
    with pytest.raises(ExternaNoDisponible) as exc:
        with traducir_errores_externa():
            raise _error(2013, "Lost connection to MySQL server during query")
    assert "no respondió" in str(exc.value)
    assert "Reintentá" in str(exc.value)


@pytest.mark.parametrize("codigo", [1044, 1045, 1142, 1143])
def test_un_acceso_rechazado_pide_avisar_a_sistemas(codigo):
    with pytest.raises(ExternaNoDisponible) as exc:
        with traducir_errores_externa():
            raise _error(codigo, "Access denied")
    assert "rechazó el acceso" in str(exc.value)
    assert "Reintentá" not in str(exc.value)


def test_un_error_sin_codigo_cuenta_como_que_no_respondio():
    with pytest.raises(ExternaNoDisponible) as exc:
        with traducir_errores_externa():
            raise OperationalError("SELECT ...", {}, Exception())
    assert "no respondió" in str(exc.value)


def test_otro_error_pasa_sin_traducir():
    with pytest.raises(ValueError):
        with traducir_errores_externa():
            raise ValueError("no es del campo")


def test_sin_error_no_hace_nada():
    with traducir_errores_externa():
        valor = 1
    assert valor == 1
