"""Fechas de alta del módulo: naive en UTC con `ahora_utc` del núcleo, sin la
API deprecada `datetime.utcnow()` (el porqué de naive, en
tests/core/test_fechas_utc.py)."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    AjusteManual, ConceptoAdicional, ConceptoLiquidacion, Preliquidacion,
    PreliquidacionLinea,
)

TOLERANCIA = timedelta(seconds=5)


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
    ahora = datetime.now(UTC).replace(tzinfo=None)
    assert abs(valor - ahora) <= TOLERANCIA, valor


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_altas_del_modulo_nacen_con_fecha_naive_utc(db):
    p = Preliquidacion(quincena=date(2026, 5, 1), creado_por=1)
    db.add(p)
    db.add(ConceptoLiquidacion(quincena=date(2026, 5, 1), tarea_nombre="COSECHA",
                               codigo=1, precio=Decimal("10")))
    db.commit()
    linea = PreliquidacionLinea(
        preliquidacion_id=p.id, nombre_tarea="COSECHA",
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"),
        hsmaquina=Decimal("0"), importe_total=Decimal("0"),
    )
    db.add(linea)
    db.commit()
    db.add(ConceptoAdicional(linea_id=linea.id, descripcion="manual", importe=Decimal("1")))
    db.add(AjusteManual(linea_id=linea.id, campo_modificado="observacion"))
    db.commit()
    db.expire_all()

    _es_naive_utc_de_ahora(db.query(Preliquidacion).one().creado_en)
    _es_naive_utc_de_ahora(db.query(ConceptoLiquidacion).one().creado_en)
    _es_naive_utc_de_ahora(db.query(ConceptoAdicional).one().fecha)
    _es_naive_utc_de_ahora(db.query(AjusteManual).one().fecha)
