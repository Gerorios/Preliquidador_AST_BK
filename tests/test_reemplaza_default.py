from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import UnidadBaseConcepto, TipoConcepto
from app.schemas.schemas import ConceptoUnifRequest
from app.api.precios import crear_concepto


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _datos(quincena, cliente_nombre=None, finca_nombre=None, reemplaza_comun=None,
           codigo=1, precio=Decimal("100")):
    return ConceptoUnifRequest(
        quincena=quincena,
        tarea_nombre="TAREA X",
        cliente_nombre=cliente_nombre,
        finca_nombre=finca_nombre,
        codigo=codigo,
        unidad_base=UnidadBaseConcepto.HSJORNAL,
        precio=precio,
        tipo=TipoConcepto.OTRO,
        categoria=None,
        reemplaza_comun=reemplaza_comun,
    )


def test_especifico_sin_mandar_reemplaza_comun_nace_true(db):
    quincena = date(2026, 5, 1)
    datos = _datos(quincena, cliente_nombre="CLIENTE A", finca_nombre="FINCA 1")

    nuevo = crear_concepto(datos=datos, db=db)

    assert nuevo.reemplaza_comun is True


def test_comun_sin_mandar_reemplaza_comun_nace_false(db):
    quincena = date(2026, 5, 1)
    datos = _datos(quincena, cliente_nombre=None, finca_nombre=None)

    nuevo = crear_concepto(datos=datos, db=db)

    assert nuevo.reemplaza_comun is False


def test_especifico_mandando_reemplaza_comun_false_explicito_respeta_false(db):
    quincena = date(2026, 5, 1)
    datos = _datos(quincena, cliente_nombre="CLIENTE A", finca_nombre="FINCA 1",
                    reemplaza_comun=False)

    nuevo = crear_concepto(datos=datos, db=db)

    assert nuevo.reemplaza_comun is False
