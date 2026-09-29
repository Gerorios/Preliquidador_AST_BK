"""Las URLs de conexión escapan la contraseña con quote_plus.

Una contraseña con caracteres reservados de URL (`@`, `:`, `/`) sin escapar
rompe el parseo de la URL de SQLAlchemy: el host o el usuario quedan mal.
"""
from app.core.config import Settings

CRUDA = "p@ss:w/ord"
ESCAPADA = "p%40ss%3Aw%2Ford"


def _settings() -> Settings:
    # Todos los obligatorios con valores ficticios; _env_file=None para no
    # leer un .env real. Los kwargs tienen prioridad sobre las variables de
    # entorno, así que el entorno de la máquina no interfiere.
    return Settings(
        _env_file=None,
        db_externa_host="externa.invalid",
        db_externa_user="u_externa",
        db_externa_password=CRUDA,
        db_externa_name="campo",
        db_sueldos_host="sueldos.invalid",
        db_sueldos_user="u_sueldos",
        db_sueldos_password=CRUDA,
        db_sueldos_name="sueldos",
        db_propia_host="propia.invalid",
        db_propia_user="u_propia",
        db_propia_password=CRUDA,
        db_propia_name="testing",
        secret_key="clave-de-test",
    )


def test_url_externa_escapa_password():
    url = _settings().url_externa
    assert ESCAPADA in url
    assert CRUDA not in url
    assert url.startswith("mysql+pymysql://u_externa:")
    assert "@externa.invalid:3306/campo" in url


def test_url_propia_escapa_password():
    url = _settings().url_propia
    assert ESCAPADA in url
    assert CRUDA not in url
    assert url.startswith("mysql+pymysql://u_propia:")
    assert "@propia.invalid:3306/testing" in url


def test_url_sueldos_escapa_password():
    url = _settings().url_sueldos
    assert ESCAPADA in url
    assert CRUDA not in url
    assert "@sueldos.invalid:3306/sueldos" in url
