"""Fechas de alta del núcleo: naive en UTC, sin la API deprecada
`datetime.utcnow()` (Python 3.12+).

Por qué naive: las columnas son `DateTime` sin zona (MySQL DATETIME y SQLite no
la guardan) y SQLAlchemy devuelve naive al leer. Un default aware haría convivir
en la misma sesión objetos aware (recién creados) con naive (cargados), y
comparar u ordenar por `creado_en` levantaría TypeError. Naive-UTC conserva
exactamente los valores que producía `utcnow()`."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import Usuario, UsuarioModulo, ahora_utc

TOLERANCIA = timedelta(seconds=5)


def _ahora_naive_utc():
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _es_naive_utc_de_ahora(valor):
    assert valor is not None
    assert valor.tzinfo is None, valor
    assert abs(valor - _ahora_naive_utc()) <= TOLERANCIA, valor


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_ahora_utc_es_naive_y_en_utc():
    _es_naive_utc_de_ahora(ahora_utc())


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_usuario_y_usuario_modulo_nacen_con_creado_en_naive_utc(db):
    u = Usuario(nombre="Liq", email="liq@t.com", password="x", rol="admin", activo=True)
    db.add(u)
    db.commit()
    db.add(UsuarioModulo(usuario_id=u.id, modulo="preliquidacion", rol="operador"))
    db.commit()
    db.expire_all()

    _es_naive_utc_de_ahora(db.query(Usuario).one().creado_en)
    _es_naive_utc_de_ahora(db.query(UsuarioModulo).one().creado_en)
