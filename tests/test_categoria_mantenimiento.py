from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    CategoriaOperario, UnidadBaseConcepto, TipoConcepto,
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
    db.add(p); db.commit(); db.refresh(p)
    return p


def _linea(db, preliq, cuit, tarea="MANTENIMIENTO MECANICO (TALLERES)", hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id, nombre_tarea=tarea, cuit=cuit,
        nombre_empleado="OPERARIO X", legajo_asignado="123",
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l); db.commit(); db.refresh(l)
    return l


def _concepto_cat(db, quincena, categoria, precio, codigo, tarea="MANTENIMIENTO MECANICO (TALLERES)"):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=None, finca_nombre=None,
        codigo=codigo, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=precio,
        tipo=TipoConcepto.JORNAL, categoria=categoria,
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_paga_el_precio_de_la_categoria_de_la_persona(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, cuit="20111111119", hsjornal=Decimal("8"))
    # Dos filas del mismo concepto, distinta categoría/precio
    _concepto_cat(db, preliq.quincena, categoria=3, precio=Decimal("100"), codigo=50)
    _concepto_cat(db, preliq.quincena, categoria=5, precio=Decimal("999"), codigo=50)
    svc = PreliquidacionService(db)

    # Sin categoría asignada -> ningún concepto por categoría aplica -> incompleta
    svc.set_categoria_operario(preliq.id, "20111111119", None)
    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")

    # Asigno categoría 3 -> toma SOLO el precio de cat 3 (100), no el de cat 5 (999)
    svc.set_categoria_operario(preliq.id, "20111111119", 3)
    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("800.00")   # 8 hsjornal * 100

    # Cambio a categoría 5 -> recalcula solo -> 8 * 999
    svc.set_categoria_operario(preliq.id, "20111111119", 5)
    db.refresh(linea)
    assert linea.importe_total == Decimal("7992.00")

    # Quito la categoría -> vuelve a incompleta, importe 0
    svc.set_categoria_operario(preliq.id, "20111111119", None)
    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")


def test_concepto_sin_categoria_no_se_afecta(db):
    """Un concepto común normal (categoria NULL) debe seguir aplicando igual
    que hoy, sin depender de ninguna asignación de categoría."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, cuit="20222222229", tarea="PODA", hsjornal=Decimal("8"))
    c = ConceptoLiquidacion(
        quincena=preliq.quincena, tarea_nombre="PODA", cliente_nombre=None, finca_nombre=None,
        codigo=10, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("50"),
        tipo=TipoConcepto.OTRO, categoria=None,
    )
    db.add(c); db.commit()
    svc = PreliquidacionService(db)

    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "PODA", "cliente_nombre": None, "finca_nombre": None},
    )
    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("400.00")   # 8 * 50, sin categoría


def test_operarios_mantenimiento_lista_por_cuil(db):
    preliq = _preliq(db)
    _linea(db, preliq, cuit="20111111119")
    _concepto_cat(db, preliq.quincena, categoria=3, precio=Decimal("100"), codigo=50)
    svc = PreliquidacionService(db)
    svc.set_categoria_operario(preliq.id, "20111111119", 3)

    ops = svc.operarios_mantenimiento(preliq.id)
    assert len(ops) == 1
    assert ops[0]["cuil"] == "20111111119"
    assert ops[0]["categoria"] == 3
