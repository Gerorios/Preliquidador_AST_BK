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


def _preliq(db, quincena=date(2026, 5, 1), valor_hora_pulv=None):
    p = Preliquidacion(quincena=quincena, creado_por=1, valor_hora_pulv=valor_hora_pulv)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente, finca, tancadas, hsjornal, hsmaquina):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        tancadas=Decimal(tancadas), hsjornal=Decimal(hsjornal), hsmaquina=Decimal(hsmaquina),
        unidades=Decimal("0"), importe_total=Decimal("0"), linea_incompleta=False,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("1")):
    """Adjunta a la línea un concepto aplicado con unidad_base = tancadas, que
    es lo que la marca como 'se paga por tancada' para el control."""
    c = ConceptoAdicional(
        linea_id=linea.id, descripcion="Tancada", tipo=TipoConcepto.OTRO,
        unidad_base="tancadas", precio=precio, cantidad=cantidad,
        importe=(cantidad * precio), ingresado_por=1,
    )
    db.add(c)
    db.commit()
    return c


def _concepto_maestro_tancada(db, quincena, tarea, cliente=None, finca=None,
                              precio=Decimal("1000"), codigo=1):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=UnidadBaseConcepto.TANCADAS, precio=precio,
        tipo=TipoConcepto.OTRO,
    )
    db.add(c)
    db.commit()
    return c


def test_control_tancadas_calcula_valores_y_diff(db):
    preliq = _preliq(db, valor_hora_pulv=Decimal("5458.34"))
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="10", hsmaquina="5")
    _aplicar_tancada(db, linea)
    _concepto_maestro_tancada(db, preliq.quincena, "PULV", "CLIENTE A", "FINCA 1",
                              precio=Decimal("1000"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] == 5458.34
    assert len(res["filas"]) == 1
    fila = res["filas"][0]
    # columnas crudas (sin /2): tal cual la suma
    assert fila["tancadas"] == 40.0
    assert fila["hsjornal"] == 10.0
    assert fila["hsmaquina"] == 5.0
    assert fila["precio"] == 1000.0
    # VALOR S/JORNAL = hsjornal/2 * (valor_hora * 1.3) = 5 * 7095.842 = 35479.21
    assert fila["valor_jornal"] == 35479.21
    # VALOR S/TANCADA = tancadas/2 * precio = 20 * 1000 = 20000
    assert fila["valor_tancada"] == 20000.0
    # DIFF = (20000 - 35479.21) / 35479.21 ≈ -0.4363 (tancada salió más barato)
    assert fila["diff"] == pytest.approx(-0.4363, abs=1e-3)

    # totales: DIFF recalculado sobre los totales (misma cuenta, una sola fila)
    tot = res["totales"]
    assert tot["valor_jornal"] == 35479.21
    assert tot["valor_tancada"] == 20000.0
    assert tot["diff"] == pytest.approx(-0.4363, abs=1e-3)


def test_sin_valor_hora_pulv_devuelve_null_no_error(db):
    preliq = _preliq(db, valor_hora_pulv=None)
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="10", hsmaquina="5")
    _aplicar_tancada(db, linea)
    _concepto_maestro_tancada(db, preliq.quincena, "PULV", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] is None
    fila = res["filas"][0]
    # sin valor hora no se puede valorizar a jornal → null (no 0, no error)
    assert fila["valor_jornal"] is None
    assert fila["diff"] is None
    # lo que sí se puede calcular sigue estando
    assert fila["valor_tancada"] == 20000.0
    assert res["totales"]["valor_jornal"] is None
    assert res["totales"]["diff"] is None


def test_hsjornal_cero_deja_diff_en_null(db):
    preliq = _preliq(db, valor_hora_pulv=Decimal("5458.34"))
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="0", hsmaquina="5")
    _aplicar_tancada(db, linea)
    _concepto_maestro_tancada(db, preliq.quincena, "PULV", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    fila = res["filas"][0]
    assert fila["valor_jornal"] == 0.0
    # jornal = 0 → no hay contra qué comparar
    assert fila["diff"] is None


def test_solo_incluye_lineas_pagadas_por_tancada(db):
    preliq = _preliq(db, valor_hora_pulv=Decimal("100"))
    # línea pagada por tancada (entra)
    l1 = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                tancadas="10", hsjornal="8", hsmaquina="4")
    _aplicar_tancada(db, l1)
    # línea sin concepto de tancada (NO entra)
    l2 = _linea(db, preliq, "OTRA", "CLIENTE B", "FINCA 2",
                tancadas="99", hsjornal="8", hsmaquina="4")
    _concepto_maestro_tancada(db, preliq.quincena, "PULV", "CLIENTE A", "FINCA 1")
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert len(res["filas"]) == 1
    assert res["filas"][0]["nombre_tarea"] == "PULV"
