"""Control Plantas vs Jornal rediseñado (grilling 2026-08-06):

- El precio por planta de cada fila sale del PAGO REAL (Σ importe / Σ cantidad
  de los conceptos adicionales con unidad "unidades"), no del maestro — así los
  caminos nuevos (por cliente / por supervisor, ADR-0011) quedan cubiertos sin
  replicar el matching del motor.
- La comparativa común vs especial se eliminó (se rearmará aparte).
- Comparativa nueva contra el "valor jornal" (jornada de 8 hs) cargado por
  quincena: jornadas = hsmaquina/8, total a jornal = jornadas × valor, con
  diferencias por totales y por jornada. Signo como en Tancadas:
  diff = (pagado por planta − a jornal) / a jornal.
"""
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


def _preliq(db, valor_jornal=None):
    p = Preliquidacion(quincena=date(2026, 8, 1), creado_por=1,
                       valor_jornal_planta=valor_jornal)
    db.add(p); db.commit(); db.refresh(p)
    return p


def _linea(db, preliq, unidades, hsmaquina, tarea="DESBROTE", cliente="CLIENTE A",
           finca="FINCA 1", supervisor=None):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id, nombre_tarea=tarea, nombre_cliente=cliente,
        nombre_finca=finca, nombre_supervisor=supervisor, grupo_pago_aplicado="PLANTA",
        unidades=Decimal(unidades), hsmaquina=Decimal(hsmaquina),
        tancadas=Decimal("0"), hsjornal=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=False,
    )
    db.add(l); db.commit(); db.refresh(l)
    return l


def _pagar(db, linea, precio, cantidad):
    db.add(ConceptoAdicional(
        linea_id=linea.id, descripcion="PLANTAS", tipo=TipoConcepto.OTRO,
        unidad_base="unidades", precio=Decimal(precio), cantidad=Decimal(cantidad),
        importe=Decimal(precio) * Decimal(cantidad), ingresado_por=1,
    )); db.commit()


def _control(db, preliq):
    return PreliquidacionService(db).control_plantas_jornal(preliq.id)


# ─── Precio desde el pago real ────────────────────────────────────────────────

def test_precio_sale_del_pago_real_no_del_maestro(db):
    """Una fila pagada por un concepto POR CLIENTE (finca NULL, ADR-0011): el
    lookup viejo contra el maestro no matcheaba (buscaba finca exacta) y
    valorizaba 0. Ahora el precio es el del pago congelado."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, unidades="1000", hsmaquina="16")
    _pagar(db, linea, precio="12", cantidad="1000")
    # Regla por cliente en el maestro (finca NULL) — no debe hacer falta
    # entenderla: el control lee el pago, no el maestro.
    db.add(ConceptoLiquidacion(
        quincena=preliq.quincena, tarea_nombre="DESBROTE",
        cliente_nombre="CLIENTE A", finca_nombre=None,
        codigo=1, unidad_base=UnidadBaseConcepto.UNIDADES,
        precio=Decimal("12"), tipo=TipoConcepto.OTRO,
    )); db.commit()

    res = _control(db, preliq)
    assert len(res["filas"]) == 1
    assert res["filas"][0]["precio_promedio"] == 12.0


def test_precio_promedio_ponderado_con_precios_mezclados(db):
    """Dos líneas del mismo grupo pagadas a precios distintos: el precio de la
    fila es el ponderado por cantidad (Σ importe / Σ cantidad)."""
    preliq = _preliq(db)
    l1 = _linea(db, preliq, unidades="600", hsmaquina="8")
    l2 = _linea(db, preliq, unidades="400", hsmaquina="8")
    _pagar(db, l1, precio="10", cantidad="600")   # 6000
    _pagar(db, l2, precio="20", cantidad="400")   # 8000

    res = _control(db, preliq)
    assert len(res["filas"]) == 1
    # (6000 + 8000) / (600 + 400) = 14
    assert res["filas"][0]["precio_promedio"] == 14.0
    assert res["filas"][0]["total_planta"] == 14000.0


def test_concepto_supervisor_no_contamina_otras_filas(db):
    """Un concepto POR SUPERVISOR (cliente NULL) en el maestro no debe tocar la
    valorización de una fila pagada con común: cada fila usa SU pago real."""
    preliq = _preliq(db)
    linea = _linea(db, preliq, unidades="100", hsmaquina="8")
    _pagar(db, linea, precio="10", cantidad="100")
    db.add(ConceptoLiquidacion(
        quincena=preliq.quincena, tarea_nombre="DESBROTE",
        cliente_nombre=None, finca_nombre=None, supervisor_nombre="JUAN",
        codigo=2, unidad_base=UnidadBaseConcepto.UNIDADES,
        precio=Decimal("99"), tipo=TipoConcepto.OTRO,
    )); db.commit()

    res = _control(db, preliq)
    assert res["filas"][0]["precio_promedio"] == 10.0


# ─── Comparativa contra el valor jornal ───────────────────────────────────────

def test_comparativa_con_valor_jornal_cargado(db):
    preliq = _preliq(db, valor_jornal=Decimal("20000"))
    linea = _linea(db, preliq, unidades="1000", hsmaquina="16")
    _pagar(db, linea, precio="10", cantidad="1000")

    res = _control(db, preliq)
    assert res["valor_jornal_planta"] == 20000.0
    f = res["filas"][0]
    assert f["unidades"] == 1000.0
    assert f["hs"] == 16.0
    assert f["plantas_por_hsm"] == 62.5
    assert f["plantas_por_hsm_x8"] == 500.0
    assert f["prom_jornal"] == 5000.0          # 500 plantas/jornada × $10
    assert f["jornadas"] == 2.0                # 16 hs / 8
    assert f["total_planta"] == 10000.0        # pagado real
    assert f["total_jornal"] == 40000.0        # 2 jornadas × $20.000
    assert f["diff_total"] == -30000.0         # planta − jornal
    assert f["diff_total_pct"] == -0.75        # (10000 − 40000) / 40000
    assert f["diff_jornada_pct"] == -0.75      # (5000 − 20000) / 20000


def test_totales_recalculados_sobre_sumas(db):
    preliq = _preliq(db, valor_jornal=Decimal("10000"))
    l1 = _linea(db, preliq, unidades="500", hsmaquina="8", finca="FINCA 1")
    l2 = _linea(db, preliq, unidades="300", hsmaquina="8", finca="FINCA 2")
    _pagar(db, l1, precio="10", cantidad="500")   # 5000
    _pagar(db, l2, precio="10", cantidad="300")   # 3000

    res = _control(db, preliq)
    t = res["totales"]
    assert t["unidades"] == 800.0
    assert t["hs"] == 16.0
    assert t["total_planta"] == 8000.0
    assert t["jornadas"] == 2.0
    assert t["total_jornal"] == 20000.0
    assert t["diff_total"] == -12000.0
    assert t["diff_total_pct"] == -0.6
    # % por jornada sobre los agregados: prom_jornal total (50×8×$10 = 4000)
    # vs valor jornal (10000) → -0.6 (coincide con el % por totales: es la
    # misma comparación en otra escala).
    assert t["diff_jornada_pct"] == -0.6


def test_sin_valor_jornal_las_comparaciones_quedan_null(db):
    preliq = _preliq(db)   # sin valor cargado
    linea = _linea(db, preliq, unidades="100", hsmaquina="8")
    _pagar(db, linea, precio="10", cantidad="100")

    res = _control(db, preliq)
    assert res["valor_jornal_planta"] is None
    f = res["filas"][0]
    assert f["jornadas"] == 1.0                 # las jornadas se muestran igual
    assert f["total_jornal"] is None
    assert f["diff_total"] is None
    assert f["diff_total_pct"] is None
    assert f["diff_jornada_pct"] is None


def test_sin_horas_maquina_no_hay_comparacion(db):
    preliq = _preliq(db, valor_jornal=Decimal("20000"))
    linea = _linea(db, preliq, unidades="100", hsmaquina="0")
    _pagar(db, linea, precio="10", cantidad="100")

    res = _control(db, preliq)
    f = res["filas"][0]
    assert f["jornadas"] == 0.0
    assert f["total_jornal"] == 0.0
    assert f["diff_total"] is None              # jornal 0: no hay contra qué comparar
    assert f["diff_total_pct"] is None
    assert f["diff_jornada_pct"] is None


# ─── La comparativa común vs especial se eliminó ──────────────────────────────

def test_columnas_comun_especial_eliminadas(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, unidades="100", hsmaquina="8")
    _pagar(db, linea, precio="10", cantidad="100")

    f = _control(db, preliq)["filas"][0]
    for clave in ("precio_comun", "precio_especial", "prom_jornal_comun",
                  "prom_jornal_especial", "var_pct"):
        assert clave not in f


# ─── Setter del valor jornal ──────────────────────────────────────────────────

def test_set_valor_jornal_planta(db):
    preliq = _preliq(db)
    svc = PreliquidacionService(db)
    actualizada = svc.set_valor_jornal_planta(preliq.id, Decimal("15000"))
    assert actualizada.valor_jornal_planta == Decimal("15000")
    actualizada = svc.set_valor_jornal_planta(preliq.id, None)   # None limpia
    assert actualizada.valor_jornal_planta is None
