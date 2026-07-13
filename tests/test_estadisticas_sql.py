from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Preliquidacion, PreliquidacionLinea
from app.services.preliquidacion_service import PreliquidacionService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, empresa=None, es_duplicado=False, alerta_legajo=False,
           linea_incompleta=False):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        empresa_asignada=empresa,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("100"),
        es_duplicado=es_duplicado, alerta_legajo=alerta_legajo,
        linea_incompleta=linea_incompleta,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def test_estadisticas_cuenta_correctamente(db):
    preliq = _preliq(db)
    # 2 líneas normales en "EMPRESA A"
    _linea(db, preliq, empresa="EMPRESA A")
    _linea(db, preliq, empresa="EMPRESA A")
    # 1 duplicada en "EMPRESA B"
    _linea(db, preliq, empresa="EMPRESA B", es_duplicado=True)
    # 1 con alerta de legajo en "EMPRESA B"
    _linea(db, preliq, empresa="EMPRESA B", alerta_legajo=True)
    # 1 incompleta sin empresa asignada (None)
    _linea(db, preliq, empresa=None, linea_incompleta=True)
    # 1 con duplicado Y alerta_legajo a la vez (no debe contarse 2 veces en lineas_con_alerta)
    _linea(db, preliq, empresa="EMPRESA A", es_duplicado=True, alerta_legajo=True)

    svc = PreliquidacionService(db)
    stats = svc.estadisticas(preliq.id)

    assert stats["total_lineas"] == 6
    assert stats["duplicados"] == 2
    assert stats["alerta_legajo"] == 2
    assert stats["incompletas"] == 1
    # con_alerta = OR de las 3 flags: duplicada(1) + alerta_legajo(1) + incompleta(1) + combinada(1) = 4
    assert stats["lineas_con_alerta"] == 4

    assert stats["por_empresa"] == {
        "EMPRESA A": {"total": 3},
        "EMPRESA B": {"total": 2},
        "SIN EMPRESA": {"total": 1},
    }


def test_estadisticas_preliquidacion_vacia(db):
    preliq = _preliq(db)
    svc = PreliquidacionService(db)
    stats = svc.estadisticas(preliq.id)

    assert stats == {
        "total_lineas": 0,
        "lineas_con_alerta": 0,
        "incompletas": 0,
        "duplicados": 0,
        "alerta_legajo": 0,
        "por_empresa": {},
    }


def test_estadisticas_batch_coincide_con_estadisticas_individual(db):
    preliq1 = _preliq(db, quincena=date(2026, 5, 1))
    preliq2 = _preliq(db, quincena=date(2026, 5, 15))

    _linea(db, preliq1, empresa="EMPRESA A")
    _linea(db, preliq1, empresa="EMPRESA A", es_duplicado=True)
    _linea(db, preliq1, empresa=None, linea_incompleta=True)

    _linea(db, preliq2, empresa="EMPRESA B", alerta_legajo=True)
    _linea(db, preliq2, empresa="EMPRESA C")

    svc = PreliquidacionService(db)

    esperado1 = svc.estadisticas(preliq1.id)
    esperado2 = svc.estadisticas(preliq2.id)

    batch = svc.estadisticas_batch([preliq1.id, preliq2.id])

    assert batch[preliq1.id] == esperado1
    assert batch[preliq2.id] == esperado2


def test_estadisticas_batch_incluye_preliquidacion_sin_lineas(db):
    preliq = _preliq(db)
    svc = PreliquidacionService(db)
    batch = svc.estadisticas_batch([preliq.id])

    assert batch[preliq.id] == svc.estadisticas(preliq.id)


def test_estadisticas_batch_lista_vacia(db):
    svc = PreliquidacionService(db)
    assert svc.estadisticas_batch([]) == {}
