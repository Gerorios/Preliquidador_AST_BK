"""ADR-0011: conceptos por cliente (cliente sin finca) y por supervisor.

Los 4 caminos de matching (común / por cliente / específico / por supervisor)
SUMAN entre sí; el tilde reemplaza_comun de cualquier regla no-común apaga
SOLO los comunes. El filtro por categoría (ADR-0008) aplica a todos los niveles.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    CategoriaOperario, UnidadBaseConcepto, TipoConcepto,
)
from app.schemas.schemas import ConceptoUnifRequest, ConceptoUnifUpdateRequest
from app.api.precios import crear_concepto, actualizar_concepto, copiar_quincena
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


def _linea(db, preliq, tarea, cliente, finca, supervisor=None, cuil=None,
           hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        nombre_supervisor=supervisor, cuit=cuil,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena, tarea, cliente=None, finca=None, supervisor=None,
              codigo=1, precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              reemplaza_comun=False, categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        supervisor_nombre=supervisor, codigo=codigo, unidad_base=unidad, precio=precio,
        tipo=TipoConcepto.OTRO, reemplaza_comun=reemplaza_comun, categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _recalcular_tarea(svc, quincena, tarea):
    """Recalcula todas las líneas de la tarea (match común: solo tarea)."""
    return svc.recalcular_por_concepto(quincena, actual={"tarea_nombre": tarea})


# ─── (a) Por cliente ─────────────────────────────────────────────────────────

def test_regla_por_cliente_aplica_en_cualquier_finca_del_cliente_y_no_en_otro_cliente(db):
    preliq = _preliq(db)
    linea_f1   = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1")
    linea_f2   = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 2")
    linea_otro = _linea(db, preliq, "TAREA X", "CLIENTE B", "FINCA 9")
    svc = PreliquidacionService(db)

    # Por cliente: cliente cargado, finca vacía
    _concepto(db, preliq.quincena, "TAREA X", cliente="CLIENTE A",
              codigo=2, precio=Decimal("30"))

    resultado = _recalcular_tarea(svc, preliq.quincena, "TAREA X")

    db.refresh(linea_f1); db.refresh(linea_f2); db.refresh(linea_otro)
    assert resultado["lineas_afectadas"] == 3
    # 8 hsjornal * 30 en las DOS fincas de CLIENTE A
    assert linea_f1.importe_total == Decimal("240.00")
    assert linea_f2.importe_total == Decimal("240.00")
    # CLIENTE B no matchea: queda incompleta y en 0
    assert linea_otro.importe_total == Decimal("0")
    assert linea_otro.linea_incompleta is True


# ─── (b) Por supervisor ──────────────────────────────────────────────────────

def test_regla_por_supervisor_aplica_solo_a_lineas_de_esa_tarea_y_supervisor(db):
    preliq = _preliq(db)
    linea_sup   = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    linea_otro  = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="GOMEZ ANA")
    linea_otra_tarea = _linea(db, preliq, "TAREA Y", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", supervisor="perez juan ",
              codigo=4, precio=Decimal("10"))  # normalizado strip().upper()

    _recalcular_tarea(svc, preliq.quincena, "TAREA X")
    _recalcular_tarea(svc, preliq.quincena, "TAREA Y")

    db.refresh(linea_sup); db.refresh(linea_otro); db.refresh(linea_otra_tarea)
    assert linea_sup.importe_total == Decimal("80.00")   # 8 * 10
    assert linea_otro.importe_total == Decimal("0")      # otro supervisor
    assert linea_otra_tarea.importe_total == Decimal("0")  # otra tarea


def test_recalculo_reactivo_de_regla_por_supervisor_solo_toca_sus_lineas(db):
    """El match reactivo (crear/editar/borrar la regla) alcanza solo las
    líneas de esa tarea con ese supervisor."""
    preliq = _preliq(db)
    linea_sup  = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="GOMEZ ANA")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"))
    resultado = svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "supervisor_nombre": "PEREZ JUAN"},
    )

    db.refresh(linea_sup)
    assert resultado["lineas_afectadas"] == 1
    assert linea_sup.importe_total == Decimal("80.00")


# ─── (c) Los 4 niveles suman ─────────────────────────────────────────────────

def test_los_cuatro_niveles_suman_en_una_linea_que_matchea_todo(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # común
    _concepto(db, preliq.quincena, "TAREA X", cliente="CLIENTE A",
              codigo=2, precio=Decimal("20"))                                  # por cliente
    _concepto(db, preliq.quincena, "TAREA X", cliente="CLIENTE A", finca="FINCA 1",
              codigo=3, precio=Decimal("30"))                                  # específico
    _concepto(db, preliq.quincena, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"))                                  # por supervisor

    _recalcular_tarea(svc, preliq.quincena, "TAREA X")

    db.refresh(linea)
    # 8 * (50 + 20 + 30 + 10) = 880
    assert linea.importe_total == Decimal("880.00")
    assert {c.codigo_concepto for c in linea.conceptos} == {1, 2, 3, 4}


# ─── (d) El tilde apaga SOLO los comunes ─────────────────────────────────────

def test_tilde_en_regla_por_cliente_apaga_solo_los_comunes(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # común
    _concepto(db, preliq.quincena, "TAREA X", cliente="CLIENTE A",
              codigo=2, precio=Decimal("20"), reemplaza_comun=True)            # por cliente con tilde
    _concepto(db, preliq.quincena, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"))                                  # por supervisor sin tilde

    _recalcular_tarea(svc, preliq.quincena, "TAREA X")

    db.refresh(linea)
    # El común (1) se descarta; por cliente (2) y por supervisor (4) siguen: 8*(20+10)
    assert linea.importe_total == Decimal("240.00")
    assert {c.codigo_concepto for c in linea.conceptos} == {2, 4}


def test_tilde_en_regla_por_supervisor_apaga_solo_los_comunes(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1", supervisor="PEREZ JUAN")
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", codigo=1, precio=Decimal("50"))  # común
    _concepto(db, preliq.quincena, "TAREA X", cliente="CLIENTE A", finca="FINCA 1",
              codigo=3, precio=Decimal("30"))                                  # específico sin tilde
    _concepto(db, preliq.quincena, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"), reemplaza_comun=True)            # supervisor con tilde

    _recalcular_tarea(svc, preliq.quincena, "TAREA X")

    db.refresh(linea)
    # Común descartado; específico y supervisor siguen sumando: 8*(30+10)
    assert linea.importe_total == Decimal("320.00")
    assert {c.codigo_concepto for c in linea.conceptos} == {3, 4}


# ─── (e) Copiar quincena preserva supervisor ─────────────────────────────────

def test_copiar_quincena_preserva_supervisor_nombre(db):
    origen, destino = date(2026, 5, 1), date(2026, 5, 16)
    _concepto(db, origen, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"))

    copiar_quincena(quincena_origen=origen, quincena_destino=destino, db=db)

    copiado = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == destino
    ).one()
    assert copiado.supervisor_nombre == "PEREZ JUAN"

    # Re-copiar no duplica: la clave de comparación incluye supervisor
    resultado = copiar_quincena(quincena_origen=origen, quincena_destino=destino, db=db)
    assert "0 copiados" in resultado.detalle


# ─── (f) Validación cliente XOR supervisor ───────────────────────────────────

def test_crear_concepto_con_cliente_y_supervisor_rechaza_422(db):
    datos = ConceptoUnifRequest(
        quincena=date(2026, 5, 1), tarea_nombre="TAREA X",
        cliente_nombre="CLIENTE A", supervisor_nombre="PEREZ JUAN",
        codigo=1, unidad_base=UnidadBaseConcepto.HSJORNAL,
        precio=Decimal("10"), tipo=TipoConcepto.OTRO,
    )
    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=datos, db=db)
    assert exc.value.status_code == 422
    assert db.query(ConceptoLiquidacion).count() == 0


def test_editar_concepto_no_puede_quedar_con_cliente_y_supervisor(db):
    quincena = date(2026, 5, 1)
    especifico = _concepto(db, quincena, "TAREA X", cliente="CLIENTE A", finca="FINCA 1",
                           codigo=3, precio=Decimal("30"))

    datos = ConceptoUnifUpdateRequest(supervisor_nombre="PEREZ JUAN")
    with pytest.raises(HTTPException) as exc:
        actualizar_concepto(concepto_id=especifico.id, datos=datos, db=db)
    assert exc.value.status_code == 422

    db.refresh(especifico)
    assert especifico.supervisor_nombre is None  # no quedó a medio guardar


def test_crear_concepto_por_supervisor_nace_con_reemplaza_comun_true(db):
    """El default del tilde pasa a 'True si NO es común': también para el
    camino por supervisor."""
    datos = ConceptoUnifRequest(
        quincena=date(2026, 5, 1), tarea_nombre="TAREA X",
        supervisor_nombre="PEREZ JUAN",
        codigo=4, unidad_base=UnidadBaseConcepto.HSJORNAL,
        precio=Decimal("10"), tipo=TipoConcepto.OTRO,
    )
    nuevo = crear_concepto(datos=datos, db=db)
    assert nuevo.reemplaza_comun is True


# ─── (g) Filtro por categoría en el nivel supervisor ─────────────────────────

def test_filtro_por_categoria_aplica_tambien_al_nivel_supervisor(db):
    preliq = _preliq(db)
    linea_cat3 = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1",
                        supervisor="PEREZ JUAN", cuil="20-111-1")
    linea_sin_cat = _linea(db, preliq, "TAREA X", "CLIENTE A", "FINCA 1",
                           supervisor="PEREZ JUAN", cuil="20-222-2")
    db.add(CategoriaOperario(quincena=preliq.quincena, cuil="20-111-1", categoria=3))
    db.commit()
    svc = PreliquidacionService(db)

    _concepto(db, preliq.quincena, "TAREA X", supervisor="PEREZ JUAN",
              codigo=4, precio=Decimal("10"), categoria=3)

    _recalcular_tarea(svc, preliq.quincena, "TAREA X")

    db.refresh(linea_cat3); db.refresh(linea_sin_cat)
    assert linea_cat3.importe_total == Decimal("80.00")   # tiene categoría 3
    assert linea_sin_cat.importe_total == Decimal("0")    # sin categoría: no matchea
    assert linea_sin_cat.linea_incompleta is True
