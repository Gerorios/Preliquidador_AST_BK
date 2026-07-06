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
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=unidad, precio=precio, tipo=TipoConcepto.OTRO,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_crear_concepto_impacta_reactivamente_la_linea_que_matchea(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert resultado["lineas_afectadas"] == 1
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("400.00")  # 8 hsjornal * 50


def test_concepto_no_afecta_lineas_de_otro_cliente(db):
    preliq = _preliq(db)
    linea_otro_cliente = _linea(db, preliq, "TAREA X", "CLIENTE Z", "FINCA 9")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea_otro_cliente)
    assert linea_otro_cliente.linea_incompleta is True  # no matcheo, sigue incompleta
    assert linea_otro_cliente.importe_total == Decimal("0")


def test_editar_claves_de_concepto_recalcula_union_viejo_y_nuevo(db):
    preliq = _preliq(db)
    linea_vieja = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    linea_nueva = _linea(db, preliq, "TAREA X", "CLIENTE B", "FINCA 2")
    svc = PreliquidacionService(db)

    concepto = _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=20, precio=Decimal("10"))
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )
    db.refresh(linea_vieja)
    assert linea_vieja.linea_incompleta is False  # matcheaba antes de la edicion

    # El liquidador edita el concepto para que ahora aplique a CLIENTE B / FINCA 2
    concepto.cliente_nombre = "CLIENTE B"
    concepto.finca_nombre = "FINCA 2"
    db.commit()

    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE B", "finca_nombre": "FINCA 2"},
        anterior={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea_vieja)
    db.refresh(linea_nueva)
    assert resultado["lineas_afectadas"] == 2  # union: la vieja (para sacarselo) + la nueva (para agregarselo)
    assert linea_vieja.linea_incompleta is True   # perdio el concepto, sin fantasma
    assert linea_vieja.importe_total == Decimal("0")
    assert linea_nueva.linea_incompleta is False  # ahora lo tiene


def test_eliminar_concepto_saca_el_importe_de_la_linea(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=30, precio=Decimal("25"))
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )
    db.refresh(linea)
    assert linea.importe_total == Decimal("200.00")  # 8 * 25

    # Se borra el concepto del maestro (la fila ya no existe) y se recalcula la linea afectada
    db.query(ConceptoLiquidacion).filter(ConceptoLiquidacion.codigo == 30).delete()
    db.commit()
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")


def test_codigo_sin_precio_no_cuenta_como_completa(db):
    """WS3 (ADR-0003): un concepto con código pero sin precio no debe
    marcar la línea como completa ni generar un ConceptoAdicional de 0."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1",
              codigo=40, precio=None)
    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert resultado["lineas_afectadas"] == 1
    assert linea.linea_incompleta is True
    assert linea.codigo_liquidacion is None
    assert linea.importe_total == Decimal("0")
    assert len(linea.conceptos) == 0


def test_sin_preliquidacion_para_la_quincena_no_falla(db):
    svc = PreliquidacionService(db)
    resultado = svc.recalcular_por_concepto(
        date(2099, 1, 1),
        actual={"tarea_nombre": "X", "cliente_nombre": None, "finca_nombre": None},
    )
    assert resultado == {"lineas_afectadas": 0}
