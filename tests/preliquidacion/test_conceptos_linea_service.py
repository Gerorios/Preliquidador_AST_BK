"""Tests de caracterización de PreliquidacionService.agregar_concepto y
agregar_concepto_por_codigo (PR3, paso 3.2).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
datos de personas son ficticios.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    ConceptoAdicional, ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea,
    TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.schemas import ConceptoAdicionalRequest
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
USUARIO = 7


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=Q1):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, **extra):
    datos = dict(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit="20000000001", nombre_empleado="PERSONA UNO", legajo_campo="0001",
        empresa_asignada="LA ASTURIANA", legajo_asignado="0001",
        fecha_tarea=date(2026, 5, 2),
        # El modelo trae linea_incompleta=True por default: se apaga explícito.
        es_duplicado=False, alerta_legajo=False, alerta_empresa=False, linea_incompleta=False,
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    datos.update(extra)
    l = PreliquidacionLinea(**datos)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto_existente(db, linea, importe):
    c = ConceptoAdicional(linea_id=linea.id, descripcion="Concepto previo", importe=Decimal(importe))
    db.add(c)
    linea.importe_total = (linea.importe_total or Decimal("0")) + Decimal(importe)
    db.commit()
    return c


def _regla(db, quincena=Q1, codigo=461, precio=Decimal("1250.50"),
           unidad=UnidadBaseConcepto.HSJORNAL):
    r = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre="TAREA X", codigo=codigo,
        unidad_base=unidad, precio=precio, tipo=TipoConcepto.REMUNERATIVO,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _pedido(importe, descripcion="Ajuste manual de prueba"):
    return ConceptoAdicionalRequest(descripcion=descripcion, importe=Decimal(importe))


# ─── agregar_concepto ─────────────────────────────────────────────────────────

def test_agregar_concepto_crea_manual_y_suma_al_total(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq)
    _concepto_existente(db, linea, "100.00")
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto(linea.id, _pedido("250.75"), USUARIO)

    assert concepto.id is not None
    assert concepto.linea_id == linea.id
    assert concepto.descripcion == "Ajuste manual de prueba"
    assert concepto.tipo == TipoConcepto.OTRO  # default del request
    assert concepto.importe == Decimal("250.75")
    assert concepto.ingresado_por == USUARIO
    # Manual: sin origen en el maestro ni snapshot de cálculo.
    assert concepto.codigo_concepto is None
    assert concepto.precio is None
    assert concepto.cantidad is None
    assert concepto.concepto_liquidacion_id is None

    db.expire_all()
    linea = db.get(PreliquidacionLinea, linea.id)
    # Fija el arreglo del comentario de agregar_concepto: el concepto recién
    # agregado SÍ entra en el total (suma anterior + importe nuevo).
    assert linea.importe_total == Decimal("350.75")
    assert linea.importe_base == Decimal("0")
    assert len(linea.conceptos) == 2


def test_agregar_concepto_total_se_recalcula_desde_conceptos_no_desde_el_campo(db):
    """El total es la suma de los conceptos existentes + el nuevo; un
    importe_total desfasado en la línea no se arrastra."""
    preliq = _preliq(db)
    linea = _linea(db, preliq)
    _concepto_existente(db, linea, "100.00")
    linea.importe_total = Decimal("999.00")
    db.commit()
    svc = PreliquidacionService(db)

    svc.agregar_concepto(linea.id, _pedido("50.00"), USUARIO)

    db.expire_all()
    assert db.get(PreliquidacionLinea, linea.id).importe_total == Decimal("150.00")


def test_agregar_concepto_segundo_suma_sobre_el_primero(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq)
    svc = PreliquidacionService(db)

    svc.agregar_concepto(linea.id, _pedido("100.00", "Primero"), USUARIO)
    svc.agregar_concepto(linea.id, _pedido("40.50", "Segundo"), USUARIO)

    db.expire_all()
    linea = db.get(PreliquidacionLinea, linea.id)
    assert linea.importe_total == Decimal("140.50")
    assert sorted(c.descripcion for c in linea.conceptos) == ["Primero", "Segundo"]


def test_agregar_concepto_linea_inexistente(db):
    svc = PreliquidacionService(db)
    with pytest.raises(ValueError, match="Línea 999 no encontrada"):
        svc.agregar_concepto(999, _pedido("10.00"), USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


# ─── agregar_concepto_por_codigo ──────────────────────────────────────────────

def test_por_codigo_calcula_desde_la_regla_del_maestro(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, hsjornal=Decimal("8"))
    _concepto_existente(db, linea, "100.00")
    regla = _regla(db, precio=Decimal("1250.50"))
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, 461, USUARIO)

    assert concepto.id is not None
    assert concepto.linea_id == linea.id
    assert concepto.importe == Decimal("10004.00")  # 8 × 1250.50
    assert concepto.cantidad == Decimal("8")
    assert concepto.precio == Decimal("1250.50")
    assert concepto.codigo_concepto == 461
    assert concepto.unidad_base == "hsjornal"
    assert concepto.tipo == TipoConcepto.REMUNERATIVO
    assert concepto.descripcion == "Concepto 461 (extra, de TAREA X)"
    assert concepto.concepto_liquidacion_id == regla.id
    # Queda como manual: ingresado_por con el usuario (lo preserva el recálculo).
    assert concepto.ingresado_por == USUARIO

    db.expire_all()
    linea = db.get(PreliquidacionLinea, linea.id)
    assert linea.importe_total == Decimal("10104.00")  # 100 previo + 10004
    assert linea.importe_base == Decimal("0")


def test_por_codigo_inexistente_en_esa_quincena(db):
    """El código existe en el maestro, pero de OTRA quincena: no vale."""
    preliq = _preliq(db, quincena=Q1)
    linea = _linea(db, preliq)
    _regla(db, quincena=Q2, codigo=461)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="No existe el código 461 en el maestro de esta quincena"):
        svc.agregar_concepto_por_codigo(linea.id, 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_por_codigo_regla_sin_precio(db):
    """Regla del código en la quincena pero con precio NULL: no hay opción
    elegible (ADR-0015), se avisa y no se escribe nada."""
    preliq = _preliq(db)
    linea = _linea(db, preliq)
    _regla(db, codigo=461, precio=None)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="El código 461 no tiene precio cargado en esta quincena"):
        svc.agregar_concepto_por_codigo(linea.id, 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_por_codigo_linea_inexistente(db):
    _regla(db)
    svc = PreliquidacionService(db)
    with pytest.raises(ValueError, match="Línea 999 no encontrada"):
        svc.agregar_concepto_por_codigo(999, 461, USUARIO)
