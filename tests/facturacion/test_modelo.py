"""El modelo TareaFacturacion sobre facturacion_tarea (plan de la E1, D4).

SQLite en memoria, como tests/core/test_fechas_utc.py: la fecha nace naive en
UTC, y una tarea del campo tiene a lo sumo una fila.
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.facturacion.models import TareaFacturacion

TOLERANCIA = timedelta(seconds=5)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_la_fila_nace_con_actualizado_en_naive_utc(db):
    db.add(TareaFacturacion(tarea_id=7, unidad_sugerida="hectareas"))
    db.commit()
    db.expire_all()

    fila = db.query(TareaFacturacion).one()
    assert fila.actualizado_en is not None
    assert fila.actualizado_en.tzinfo is None, fila.actualizado_en
    ahora = datetime.now(UTC).replace(tzinfo=None)
    assert abs(fila.actualizado_en - ahora) <= TOLERANCIA, fila.actualizado_en
    # Sin persona: la fila la cargó el script de la primera carga.
    assert fila.actualizado_por is None
    assert fila.no_facturable is False


def test_una_tarea_tiene_a_lo_sumo_una_fila(db):
    db.add(TareaFacturacion(tarea_id=7, unidad_sugerida="hectareas"))
    db.commit()

    db.add(TareaFacturacion(tarea_id=7, no_facturable=True))
    with pytest.raises(IntegrityError):
        db.commit()
