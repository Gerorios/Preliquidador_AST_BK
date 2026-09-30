"""Comparación del modelo contra el esquema real de la base (PR2, paso 2.1).

El riesgo que se ataca: deployar código que necesita una tabla o columna que
la base todavía no tiene (migración sin aplicar). Se compara sólo por nombres;
tipos e índices quedan afuera porque MySQL y el ORM los describen distinto y
darían falsos positivos.
"""
import pytest
from sqlalchemy import create_engine, inspect, text

# Importar app.main registra en Base.metadata las tablas del núcleo y las de
# los módulos activos, igual que al arrancar la app.
import app.main  # noqa: F401
from app.core.database import Base
from app.core.esquema import comparar_esquema


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_esquema_completo_no_reporta_nada(engine):
    diferencias = comparar_esquema(Base.metadata, inspect(engine))

    assert diferencias.tablas_faltantes == []
    assert diferencias.columnas_faltantes == []


def test_reporta_tabla_y_columna_faltantes_ordenadas(engine):
    with engine.begin() as con:
        con.execute(text("DROP TABLE usuario_modulo"))
        con.execute(text("ALTER TABLE usuarios DROP COLUMN nombre"))
        con.execute(text("ALTER TABLE usuarios DROP COLUMN creado_en"))

    diferencias = comparar_esquema(Base.metadata, inspect(engine))

    assert diferencias.tablas_faltantes == ["usuario_modulo"]
    assert diferencias.columnas_faltantes == ["usuarios.creado_en", "usuarios.nombre"]


def test_columnas_y_tablas_de_mas_en_la_base_no_son_error(engine):
    # Producción puede tener columnas viejas deprecadas y tablas ajenas
    # (testing es compartida con otros sistemas): no son un deploy incompleto.
    with engine.begin() as con:
        con.execute(text("ALTER TABLE usuarios ADD COLUMN columna_deprecada TEXT"))
        con.execute(text("CREATE TABLE tabla_ajena (id INTEGER PRIMARY KEY)"))

    diferencias = comparar_esquema(Base.metadata, inspect(engine))

    assert diferencias.tablas_faltantes == []
    assert diferencias.columnas_faltantes == []
