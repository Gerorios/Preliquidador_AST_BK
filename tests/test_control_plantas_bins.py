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
    db.add(p); db.commit(); db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente, finca, grupo_pago, unidades, hsmaquina):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id, nombre_tarea=tarea, nombre_cliente=cliente,
        nombre_finca=finca, grupo_pago_aplicado=grupo_pago,
        unidades=Decimal(unidades), hsmaquina=Decimal(hsmaquina),
        tancadas=Decimal("0"), hsjornal=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=False,
    )
    db.add(l); db.commit(); db.refresh(l)
    return l


def _aplicar_unidades(db, linea, precio=Decimal("10"), cantidad=Decimal("1")):
    """Concepto aplicado con unidad_base = 'unidades' (lo que hoy hace que la
    línea entre al control, tanto plantas como bins)."""
    db.add(ConceptoAdicional(
        linea_id=linea.id, descripcion="U", tipo=TipoConcepto.OTRO,
        unidad_base="unidades", precio=precio, cantidad=cantidad,
        importe=(cantidad * precio), ingresado_por=1,
    )); db.commit()


def test_plantas_vs_jornal_excluye_carga_por_bins(db):
    preliq = _preliq(db)
    # Trabajo de PLANTA (debe aparecer)
    l_planta = _linea(db, preliq, "PODA", "CLIENTE A", "FINCA 1",
                      grupo_pago="PLANTA", unidades="100", hsmaquina="5")
    _aplicar_unidades(db, l_planta)
    # Carga de fruta por BINS: también se paga por unidades, pero NO es planta
    l_bins = _linea(db, preliq, "CARGA FRUTA BINS", "CLIENTE B", "FINCA 2",
                    grupo_pago="BINS", unidades="80", hsmaquina="4")
    _aplicar_unidades(db, l_bins)
    # precio del maestro para la tarea de planta
    db.add(ConceptoLiquidacion(
        quincena=preliq.quincena, tarea_nombre="PODA", cliente_nombre=None, finca_nombre=None,
        codigo=1, unidad_base=UnidadBaseConcepto.UNIDADES, precio=Decimal("10"), tipo=TipoConcepto.OTRO,
    )); db.commit()

    svc = PreliquidacionService(db)
    res = svc.control_plantas_jornal(preliq.id)

    tareas = {f["nombre_tarea"] for f in res["filas"]}
    assert "PODA" in tareas                      # planta entra
    assert "CARGA FRUTA BINS" not in tareas       # bins NO entra
    assert len(res["filas"]) == 1
