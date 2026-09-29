"""Fixtures compartidas por toda la suite."""
import pytest

from app.core.limite_login import limitador_login


@pytest.fixture(autouse=True)
def _limitador_login_limpio():
    # El limitador de intentos de login es estado del proceso: sin esto, los
    # logins fallidos de un test (test_login_cuil, test_cambiar_password,
    # test_administracion, ...) se acumulan en los siguientes y alguno termina
    # recibiendo un 429 que no busca.
    limitador_login.limpiar()
    yield
