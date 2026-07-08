from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    UnidadBaseConcepto, TipoConcepto,
)
from app.api.precios import copiar_quincena, actualizar_concepto
from app.schemas.schemas import ConceptoUnifUpdateRequest


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente, finca, hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena, tarea, cliente=None, finca=None, codigo=1,
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL, heredado=False):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=unidad, precio=precio, tipo=TipoConcepto.OTRO,
        heredado=heredado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


QUINCENA_ORIGEN = date(2026, 5, 1)
QUINCENA_DESTINO = date(2026, 5, 16)


def test_copiar_marca_los_nuevos_conceptos_como_heredados(db):
    _concepto(db, QUINCENA_ORIGEN, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))

    copiar_quincena(quincena_origen=QUINCENA_ORIGEN, quincena_destino=QUINCENA_DESTINO, db=db)

    nuevo = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == QUINCENA_DESTINO
    ).first()
    assert nuevo is not None
    assert nuevo.heredado is True
    # el origen no se toca
    original = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == QUINCENA_ORIGEN
    ).first()
    assert original.heredado is False


def test_copiar_a_quincena_con_preliquidacion_generada_autoaplica_sin_pasos_manuales(db):
    _concepto(db, QUINCENA_ORIGEN, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))

    preliq_destino = _preliq(db, QUINCENA_DESTINO)
    linea = _linea(db, preliq_destino, "TAREA X", "CLIENTE A", "FINCA 1")
    assert linea.linea_incompleta is True

    resultado = copiar_quincena(quincena_origen=QUINCENA_ORIGEN, quincena_destino=QUINCENA_DESTINO, db=db)

    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("400.00")  # 8 hsjornal * 50
    assert "recalculadas" in (resultado.detalle or "")


def test_copiar_sin_preliquidacion_destino_no_falla(db):
    _concepto(db, QUINCENA_ORIGEN, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))

    resultado = copiar_quincena(quincena_origen=QUINCENA_ORIGEN, quincena_destino=QUINCENA_DESTINO, db=db)

    assert resultado.mensaje == "Conceptos copiados"
    copiado = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == QUINCENA_DESTINO
    ).first()
    assert copiado.heredado is True


def test_editar_precio_de_heredado_limpia_la_marca(db):
    concepto = _concepto(db, QUINCENA_DESTINO, "TAREA X", "CLIENTE A", "FINCA 1",
                          codigo=10, precio=Decimal("50"), heredado=True)

    actualizar_concepto(
        concepto_id=concepto.id,
        datos=ConceptoUnifUpdateRequest(precio=Decimal("75")),
        db=db,
    )

    db.refresh(concepto)
    assert concepto.heredado is False
    assert concepto.precio == Decimal("75")


def test_editar_otro_campo_de_heredado_no_toca_la_marca(db):
    concepto = _concepto(db, QUINCENA_DESTINO, "TAREA X", "CLIENTE A", "FINCA 1",
                          codigo=10, precio=Decimal("50"), heredado=True)

    actualizar_concepto(
        concepto_id=concepto.id,
        datos=ConceptoUnifUpdateRequest(tipo=TipoConcepto.REMUNERATIVO),
        db=db,
    )

    db.refresh(concepto)
    assert concepto.heredado is True
    assert concepto.tipo == TipoConcepto.REMUNERATIVO
