"""Tests de caracterización de PreliquidacionService.recalcular_por_categoria y
heredar_categorias_operario (Mantenimiento mecánico por categoría, ADR-0008;
PR3, paso 3.4).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
CUIL y nombres son ficticios.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    CategoriaOperario, ConceptoAdicional, ConceptoLiquidacion, Preliquidacion,
    PreliquidacionLinea, TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

TALLER = "MANTENIMIENTO MECANICO (TALLERES)"
Q_ACTUAL = date(2026, 5, 1)
CUIL_A = "20111111119"
CUIL_B = "20222222229"
CUIL_C = "20333333339"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=Q_ACTUAL):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p); db.commit(); db.refresh(p)
    return p


def _linea(db, preliq, cuit, tarea=TALLER, hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id, nombre_tarea=tarea, cuit=cuit,
        nombre_empleado="OPERARIO FICTICIO", legajo_asignado="123",
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l); db.commit(); db.refresh(l)
    return l


def _concepto(db, quincena, categoria, precio, codigo, tarea=TALLER):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=None, finca_nombre=None,
        codigo=codigo, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=precio,
        tipo=TipoConcepto.JORNAL, categoria=categoria,
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def _asignar(db, quincena, cuil, categoria):
    """Inserta la asignación directo en la tabla (sin set_categoria_operario,
    que además dispara el recálculo)."""
    a = CategoriaOperario(quincena=quincena, cuil=cuil, categoria=categoria)
    db.add(a); db.commit()
    return a


def _asignaciones(db, quincena):
    rows = db.query(CategoriaOperario).filter(CategoriaOperario.quincena == quincena).all()
    return {r.cuil: r.categoria for r in rows}


def _automaticos(db, linea):
    return db.query(ConceptoAdicional).filter(
        ConceptoAdicional.linea_id == linea.id,
        ConceptoAdicional.ingresado_por.is_(None),
    ).all()


# ─── recalcular_por_categoria ────────────────────────────────────────────────

def test_recalcular_sin_preliquidacion_de_la_quincena_devuelve_cero(db):
    # Hay maestro por categoría y asignación, pero ninguna preliquidación
    # con esa quincena: no hay líneas que tocar.
    _concepto(db, Q_ACTUAL, categoria=3, precio=Decimal("100"), codigo=50)
    _asignar(db, Q_ACTUAL, CUIL_A, 3)
    svc = PreliquidacionService(db)

    assert svc.recalcular_por_categoria(Q_ACTUAL, CUIL_A) == {"lineas_afectadas": 0}


def test_recalcular_sin_tareas_con_categoria_en_el_maestro_devuelve_cero(db):
    # El maestro de la quincena tiene la tarea, pero sin categoría (común):
    # no es "taller", así que recalcular_por_categoria no toca nada. Corta
    # antes de _aplicar_conceptos_a_lineas: el dict no trae actualizadas.
    preliq = _preliq(db)
    linea = _linea(db, preliq, CUIL_A)
    _concepto(db, Q_ACTUAL, categoria=None, precio=Decimal("100"), codigo=50)
    _asignar(db, Q_ACTUAL, CUIL_A, 3)
    svc = PreliquidacionService(db)

    assert svc.recalcular_por_categoria(Q_ACTUAL, CUIL_A) == {"lineas_afectadas": 0}
    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")
    assert _automaticos(db, linea) == []


def test_recalcular_aplica_el_concepto_de_la_categoria_a_la_linea_de_ese_cuil(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, CUIL_A, hsjornal=Decimal("8"))
    otra_tarea_mismo_cuil = _linea(db, preliq, CUIL_A, tarea="PODA")
    otro_cuil = _linea(db, preliq, CUIL_B)
    regla = _concepto(db, Q_ACTUAL, categoria=3, precio=Decimal("100"), codigo=50)
    _concepto(db, Q_ACTUAL, categoria=5, precio=Decimal("999"), codigo=50)
    _asignar(db, Q_ACTUAL, CUIL_A, 3)
    svc = PreliquidacionService(db)

    resultado = svc.recalcular_por_categoria(Q_ACTUAL, CUIL_A)

    # Sólo la línea de taller de CUIL_A: ni la de otra tarea ni la de otro CUIL.
    assert resultado["lineas_afectadas"] == 1
    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("800.00")   # 8 hsjornal * 100 (cat 3)
    autos = _automaticos(db, linea)
    assert len(autos) == 1
    assert autos[0].concepto_liquidacion_id == regla.id
    assert autos[0].codigo_concepto == 50

    # Las otras dos quedan como estaban (incompletas, sin conceptos).
    for intacta in (otra_tarea_mismo_cuil, otro_cuil):
        db.refresh(intacta)
        assert intacta.linea_incompleta is True
        assert intacta.importe_total == Decimal("0")
        assert _automaticos(db, intacta) == []


def test_recalcular_compara_el_cuil_con_trim(db):
    # La línea trae el CUIL con espacios y el parámetro también: la query
    # compara upper(trim(cuit)) contra el parámetro normalizado, y el filtro
    # por categoría usa cuit.strip(), así que la línea igual cobra.
    # (upper no se puede ejercitar con un CUIL numérico; queda sin probar.)
    preliq = _preliq(db)
    linea = _linea(db, preliq, f"  {CUIL_A} ")
    _concepto(db, Q_ACTUAL, categoria=3, precio=Decimal("100"), codigo=50)
    _asignar(db, Q_ACTUAL, CUIL_A, 3)
    svc = PreliquidacionService(db)

    resultado = svc.recalcular_por_categoria(Q_ACTUAL, f" {CUIL_A}  ")

    assert resultado["lineas_afectadas"] == 1
    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("800.00")


# ─── heredar_categorias_operario ─────────────────────────────────────────────

def test_heredar_preliquidacion_inexistente_levanta_value_error(db):
    svc = PreliquidacionService(db)
    with pytest.raises(ValueError, match="Preliquidacion 999 no encontrada"):
        svc.heredar_categorias_operario(999)


def test_heredar_sin_asignaciones_anteriores_devuelve_cero(db):
    preliq = _preliq(db)
    # Una asignación POSTERIOR a la quincena actual no cuenta como "anterior".
    _asignar(db, date(2026, 6, 1), CUIL_A, 3)
    svc = PreliquidacionService(db)

    assert svc.heredar_categorias_operario(preliq.id) == {"heredados": 0}
    assert _asignaciones(db, Q_ACTUAL) == {}


def test_heredar_toma_la_mayor_quincena_anterior_y_solo_cuils_sin_asignacion(db):
    preliq = _preliq(db)                       # quincena actual: 2026-05-01
    linea_a = _linea(db, preliq, CUIL_A, hsjornal=Decimal("8"))
    linea_b = _linea(db, preliq, CUIL_B, hsjornal=Decimal("8"))
    _concepto(db, Q_ACTUAL, categoria=3, precio=Decimal("100"), codigo=50)
    _concepto(db, Q_ACTUAL, categoria=5, precio=Decimal("999"), codigo=50)

    # Dos quincenas previas con asignaciones. La inmediata (2026-04-16) no
    # tiene ninguna: se toma la mayor con datos (2026-04-01), no la inmediata.
    vieja = date(2026, 3, 1)
    mayor_anterior = date(2026, 4, 1)
    _asignar(db, vieja, CUIL_A, 5)
    _asignar(db, vieja, CUIL_C, 5)             # sólo en la vieja: NO se hereda
    _asignar(db, mayor_anterior, CUIL_A, 3)
    _asignar(db, mayor_anterior, CUIL_B, 3)
    # CUIL_B ya tiene asignación en la actual: no se pisa.
    _asignar(db, Q_ACTUAL, CUIL_B, 5)
    svc = PreliquidacionService(db)

    resultado = svc.heredar_categorias_operario(preliq.id)

    assert resultado == {"heredados": 1}
    # CUIL_A heredó la categoría de la mayor anterior (3, no la 5 de la vieja);
    # CUIL_B conserva la suya (5); CUIL_C no aparece.
    assert _asignaciones(db, Q_ACTUAL) == {CUIL_A: 3, CUIL_B: 5}

    # La línea de taller de CUIL_A se recalculó con la categoría heredada.
    db.refresh(linea_a)
    assert linea_a.linea_incompleta is False
    assert linea_a.importe_total == Decimal("800.00")   # 8 * 100 (cat 3)

    # La de CUIL_B no la recalcula heredar (no es un CUIL heredado): sigue
    # como estaba aunque tenga asignación en la actual.
    db.refresh(linea_b)
    assert linea_b.linea_incompleta is True
    assert linea_b.importe_total == Decimal("0")
    assert _automaticos(db, linea_b) == []


def test_heredar_es_idempotente(db):
    # Una segunda llamada no duplica: todos los CUIL ya tienen asignación
    # en la actual (y la UniqueConstraint quincena+cuil no se viola).
    preliq = _preliq(db)
    _asignar(db, date(2026, 4, 16), CUIL_A, 3)
    svc = PreliquidacionService(db)

    assert svc.heredar_categorias_operario(preliq.id) == {"heredados": 1}
    assert svc.heredar_categorias_operario(preliq.id) == {"heredados": 0}
    assert _asignaciones(db, Q_ACTUAL) == {CUIL_A: 3}
