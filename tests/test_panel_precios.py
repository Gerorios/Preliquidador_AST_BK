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
from app.schemas.schemas import ConceptoPrecioMasivoRequest
from app.api.precios import panel_conceptos, precio_masivo


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
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL, categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=unidad, precio=precio, tipo=TipoConcepto.OTRO,
        categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _aplicar_concepto(db, linea, unidad_base, precio, cantidad=Decimal("1")):
    c = ConceptoAdicional(
        linea_id=linea.id, descripcion="auto", tipo=TipoConcepto.OTRO,
        unidad_base=unidad_base, precio=precio, cantidad=cantidad,
        importe=(cantidad * precio), ingresado_por=1,
    )
    db.add(c)
    db.commit()
    return c


# ─── GET /conceptos/panel ─────────────────────────────────────────────────────

def test_panel_devuelve_precio_anterior_de_la_quincena_previa(db):
    quincena_anterior = date(2026, 4, 1)
    quincena_actual = date(2026, 5, 1)

    _concepto(db, quincena_anterior, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    actual = _concepto(db, quincena_actual, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("80"))

    resultado = panel_conceptos(quincena=quincena_actual, db=db)

    assert len(resultado) == 1
    fila = resultado[0]
    assert fila.id == actual.id
    assert fila.precio == Decimal("80")
    assert fila.precio_anterior == Decimal("50")


def test_panel_precio_anterior_null_si_no_existia_en_quincena_previa(db):
    quincena_anterior = date(2026, 4, 1)
    quincena_actual = date(2026, 5, 1)

    # la quincena anterior tiene conceptos, pero ninguno con esta clave exacta
    _concepto(db, quincena_anterior, "OTRA TAREA", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    _concepto(db, quincena_actual, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("80"))

    resultado = panel_conceptos(quincena=quincena_actual, db=db)

    assert len(resultado) == 1
    assert resultado[0].precio_anterior is None


def test_panel_precio_anterior_null_si_no_hay_quincena_previa(db):
    quincena_actual = date(2026, 5, 1)
    _concepto(db, quincena_actual, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("80"))

    resultado = panel_conceptos(quincena=quincena_actual, db=db)

    assert len(resultado) == 1
    assert resultado[0].precio_anterior is None


def test_panel_incluye_comunes_y_especificos_juntos(db):
    quincena = date(2026, 5, 1)
    _concepto(db, quincena, "TAREA X", cliente=None, finca=None, codigo=1, precio=Decimal("10"))
    _concepto(db, quincena, "TAREA X", cliente="CLIENTE A", finca="FINCA 1", codigo=2, precio=Decimal("20"))

    resultado = panel_conceptos(quincena=quincena, db=db)

    assert len(resultado) == 2
    heredados = {(f.codigo, f.cliente_nombre) for f in resultado}
    assert (1, None) in heredados
    assert (2, "CLIENTE A") in heredados


# ─── PATCH /conceptos/precio-masivo ───────────────────────────────────────────

def test_precio_masivo_setea_precio_saca_heredado_y_recalcula(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")

    c1 = _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    c1.heredado = True
    db.commit()

    resultado = precio_masivo(
        datos=ConceptoPrecioMasivoRequest(ids=[c1.id], precio=Decimal("99")),
        db=db,
    )

    assert resultado.actualizados == 1
    assert resultado.lineas_afectadas == 1

    db.refresh(c1)
    assert c1.precio == Decimal("99")
    assert c1.heredado is False

    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("792.00")  # 8 hsjornal * 99


def test_precio_masivo_batchea_varios_ids_en_un_solo_recalculo(db):
    preliq = _preliq(db)
    linea_a = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    linea_b = _linea(db, preliq, "TAREA Y", "CLIENTE B", "FINCA 2")

    c1 = _concepto(db, preliq.quincena, "TAREA X", "CLIENTE A", "FINCA 1", codigo=10, precio=Decimal("50"))
    c2 = _concepto(db, preliq.quincena, "TAREA Y", "CLIENTE B", "FINCA 2", codigo=20, precio=Decimal("30"))

    resultado = precio_masivo(
        datos=ConceptoPrecioMasivoRequest(ids=[c1.id, c2.id], precio=Decimal("40")),
        db=db,
    )

    assert resultado.actualizados == 2
    assert resultado.lineas_afectadas == 2

    db.refresh(c1); db.refresh(c2)
    assert c1.precio == Decimal("40")
    assert c2.precio == Decimal("40")

    db.refresh(linea_a); db.refresh(linea_b)
    assert linea_a.importe_total == Decimal("320.00")  # 8 * 40
    assert linea_b.importe_total == Decimal("320.00")  # 8 * 40


def test_precio_masivo_sin_ids_encontrados_da_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        precio_masivo(datos=ConceptoPrecioMasivoRequest(ids=[999], precio=Decimal("1")), db=db)
    assert exc.value.status_code == 404


# ─── control_plantas_jornal: precio_comun / precio_especial ──────────────────

def test_control_plantas_separa_precio_comun_y_especial(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "PLANTACION", "CLIENTE A", "FINCA 1")
    linea.unidades = Decimal("800")
    linea.hsmaquina = Decimal("8")
    db.commit()
    _aplicar_concepto(db, linea, "unidades", precio=Decimal("2"))

    _concepto(db, preliq.quincena, "PLANTACION", cliente=None, finca=None,
              codigo=1, precio=Decimal("2"), unidad=UnidadBaseConcepto.UNIDADES)
    _concepto(db, preliq.quincena, "PLANTACION", cliente="CLIENTE A", finca="FINCA 1",
              codigo=2, precio=Decimal("3"), unidad=UnidadBaseConcepto.UNIDADES)

    svc = PreliquidacionService(db)
    resultado = svc.control_plantas_jornal(preliq.id)

    fila = resultado["filas"][0]
    assert fila["precio_comun"] == 2.0
    assert fila["precio_especial"] == 3.0
    assert fila["var_pct"] == pytest.approx(0.5, abs=1e-4)  # (3-2)/2
    phsm = 800 / 8
    assert fila["prom_jornal_comun"] == round(phsm * 8 * 2, 2)
    assert fila["prom_jornal_especial"] == round(phsm * 8 * 3, 2)


def test_control_plantas_precio_especial_null_si_no_hay_especifico(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "PLANTACION", "CLIENTE A", "FINCA 1")
    linea.unidades = Decimal("800")
    linea.hsmaquina = Decimal("8")
    db.commit()
    _aplicar_concepto(db, linea, "unidades", precio=Decimal("2"))

    _concepto(db, preliq.quincena, "PLANTACION", cliente=None, finca=None,
              codigo=1, precio=Decimal("2"), unidad=UnidadBaseConcepto.UNIDADES)

    svc = PreliquidacionService(db)
    resultado = svc.control_plantas_jornal(preliq.id)

    fila = resultado["filas"][0]
    assert fila["precio_comun"] == 2.0
    assert fila["precio_especial"] is None
    assert fila["var_pct"] is None
    assert fila["prom_jornal_especial"] is None


# ─── control_tancadas_jornal: precio_comun / precio_especial ─────────────────

def test_control_tancadas_separa_precio_comun_y_especial(db):
    preliq = _preliq(db, )
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1")
    linea.tancadas = Decimal("40")
    linea.hsjornal = Decimal("10")
    linea.hsmaquina = Decimal("5")
    db.commit()
    _aplicar_concepto(db, linea, "tancadas", precio=Decimal("1000"))

    _concepto(db, preliq.quincena, "PULV", cliente=None, finca=None,
              codigo=1, precio=Decimal("1000"), unidad=UnidadBaseConcepto.TANCADAS)
    _concepto(db, preliq.quincena, "PULV", cliente="CLIENTE A", finca="FINCA 1",
              codigo=2, precio=Decimal("1200"), unidad=UnidadBaseConcepto.TANCADAS)

    svc = PreliquidacionService(db)
    resultado = svc.control_tancadas_jornal(preliq.id)

    fila = resultado["filas"][0]
    assert fila["precio_comun"] == 1000.0
    assert fila["precio_especial"] == 1200.0
    assert fila["var_pct"] == pytest.approx(0.2, abs=1e-4)  # (1200-1000)/1000
    # tancadas/2 * precio
    assert fila["valor_tancada_comun"] == 20000.0
    assert fila["valor_tancada_especial"] == 24000.0
