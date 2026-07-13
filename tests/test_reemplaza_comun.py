from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    ConceptoAdicional, UnidadBaseConcepto, TipoConcepto,
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
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              reemplaza_comun=False):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=unidad, precio=precio, tipo=TipoConcepto.OTRO,
        reemplaza_comun=reemplaza_comun,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_comun_y_especifico_sin_tilde_suman(db):
    """Comportamiento actual intacto: común + específico sin reemplaza_comun
    se suman (default False)."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # comun
    _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=2, precio=Decimal("30"))  # especifico

    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert resultado["lineas_afectadas"] == 1
    # 8 hsjornal * 50 (comun) + 8 hsjornal * 30 (especifico) = 400 + 240 = 640
    assert linea.importe_total == Decimal("640.00")
    assert len(linea.conceptos) == 2


def test_especifico_con_tilde_descarta_el_comun(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # comun
    _concepto(
        db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1",
        codigo=2, precio=Decimal("30"), reemplaza_comun=True,
    )  # especifico con tilde

    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert resultado["lineas_afectadas"] == 1
    # Solo el especifico: 8 hsjornal * 30 = 240. El comun NO se aplica.
    assert linea.importe_total == Decimal("240.00")
    assert len(linea.conceptos) == 1
    assert linea.conceptos[0].codigo_concepto == 2
    # Verifica explicitamente que no hay ConceptoAdicional del comun (codigo 1)
    codigos_aplicados = {c.codigo_concepto for c in linea.conceptos}
    assert 1 not in codigos_aplicados


def test_otra_finca_misma_tarea_sin_especifico_sigue_cobrando_el_comun(db):
    """El tilde de un especifico de FINCA 1 no afecta a otra finca de la
    misma tarea que no tiene concepto especifico propio."""
    preliq = _preliq(db)
    linea_con_tilde = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    linea_otra_finca = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 2")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # comun
    _concepto(
        db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1",
        codigo=2, precio=Decimal("30"), reemplaza_comun=True,
    )

    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )
    # Tambien recalculamos explicitamente la otra finca (no matchea el especifico,
    # asi que igual deberia seguir cobrando el comun con el flujo normal de generacion)
    resultado_otra = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 2"},
    )

    db.refresh(linea_con_tilde)
    db.refresh(linea_otra_finca)

    assert linea_con_tilde.importe_total == Decimal("240.00")  # solo especifico
    assert resultado_otra["lineas_afectadas"] == 1
    assert linea_otra_finca.importe_total == Decimal("400.00")  # 8 * 50, solo el comun
    assert len(linea_otra_finca.conceptos) == 1
    assert linea_otra_finca.conceptos[0].codigo_concepto == 1


def test_reemplazo_via_recalculo_reactivo(db):
    """El reemplazo tambien vale cuando se dispara desde recalcular_por_concepto
    (ej. tras crear/editar un concepto en el maestro), no solo en la generacion inicial."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # comun
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )
    db.refresh(linea)
    assert linea.importe_total == Decimal("400.00")  # solo el comun por ahora
    assert len(linea.conceptos) == 1

    # Ahora se crea el especifico con el tilde -> dispara el recalculo reactivo
    _concepto(
        db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1",
        codigo=2, precio=Decimal("30"), reemplaza_comun=True,
    )
    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert resultado["lineas_afectadas"] == 1
    assert linea.importe_total == Decimal("240.00")  # el comun quedo descartado
    assert len(linea.conceptos) == 1
    assert linea.conceptos[0].codigo_concepto == 2
