"""Tests de caracterización de PreliquidacionService.agregar_concepto_masivo,
eliminar_concepto_masivo y sus endpoints POST /api/preliquidacion/lineas/
concepto-masivo y /concepto-masivo/eliminar (PR3, paso 3.3).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
datos de personas son ficticios.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base, get_db_externa, get_db_propia, get_db_sueldos
from app.main import app
from app.modulos.preliquidacion.models import (
    ConceptoAdicional, ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea,
    TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
USUARIO = 7
URL_AGREGAR = "/api/preliquidacion/lineas/concepto-masivo"
URL_ELIMINAR = "/api/preliquidacion/lineas/concepto-masivo/eliminar"


@pytest.fixture()
def db():
    # StaticPool + check_same_thread=False: el TestClient ejecuta los
    # endpoints en otro thread y la SQLite in-memory vive por conexión.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def cliente(db):
    admin = SimpleNamespace(
        id=USUARIO, nombre="Admin Prueba", email="admin@ejemplo.test",
        rol="admin", activo=True, modulos=[],
    )
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    # get_service declara las 3 sesiones: todas apuntan a la sqlite.
    app.dependency_overrides[get_db_propia] = lambda: db
    app.dependency_overrides[get_db_externa] = lambda: db
    app.dependency_overrides[get_db_sueldos] = lambda: db
    # Sin `with`: no corre el lifespan (que verifica las conexiones reales).
    yield TestClient(app)
    app.dependency_overrides.clear()


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


def _concepto_existente(db, linea, importe, codigo=None):
    c = ConceptoAdicional(
        linea_id=linea.id, descripcion=f"Concepto previo {codigo}",
        codigo_concepto=codigo, importe=Decimal(importe),
    )
    db.add(c)
    linea.importe_total = (linea.importe_total or Decimal("0")) + Decimal(importe)
    db.commit()
    return c


def _regla(db, quincena=Q1, codigo=461, precio=Decimal("1000.00"),
           unidad=UnidadBaseConcepto.HSJORNAL):
    r = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre="TAREA X", codigo=codigo,
        unidad_base=unidad, precio=precio, tipo=TipoConcepto.REMUNERATIVO,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _tres_lineas(db, preliq):
    l1 = _linea(db, preliq, hsjornal=Decimal("8"), nombre_empleado="PERSONA UNO")
    l2 = _linea(db, preliq, hsjornal=Decimal("4"), nombre_empleado="PERSONA DOS",
                cuit="20000000002", legajo_campo="0002", legajo_asignado="0002")
    l3 = _linea(db, preliq, hsjornal=Decimal("2.5"), nombre_empleado="PERSONA TRES",
                cuit="20000000003", legajo_campo="0003", legajo_asignado="0003")
    return l1, l2, l3


# ─── agregar_concepto_masivo ──────────────────────────────────────────────────

def test_masivo_aplica_a_todas_las_lineas(db):
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)
    _concepto_existente(db, l1, "100.00")
    regla = _regla(db, precio=Decimal("1000.00"))
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo([l1.id, l2.id, l3.id], 461, USUARIO)

    assert resultado == {"aplicadas": 3}
    db.expire_all()
    esperado = {  # linea_id: (importe del concepto nuevo, importe_total)
        l1.id: (Decimal("8000.00"), Decimal("8100.00")),  # 100 previo + 8 × 1000
        l2.id: (Decimal("4000.00"), Decimal("4000.00")),
        l3.id: (Decimal("2500.00"), Decimal("2500.00")),
    }
    for linea_id, (importe, total) in esperado.items():
        linea = db.get(PreliquidacionLinea, linea_id)
        masivos = [c for c in linea.conceptos if c.codigo_concepto == 461]
        assert len(masivos) == 1
        c = masivos[0]
        assert c.descripcion == "Concepto 461 (masivo)"
        assert c.importe == importe
        assert c.precio == Decimal("1000.00")
        assert c.unidad_base == "hsjornal"
        assert c.tipo == TipoConcepto.REMUNERATIVO
        assert c.concepto_liquidacion_id == regla.id
        assert c.ingresado_por == USUARIO
        assert linea.importe_total == total
        assert linea.importe_base == Decimal("0")


def test_masivo_saltea_ids_inexistentes_y_no_los_cuenta(db):
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo([l1.id, 999, l2.id], 461, USUARIO)

    assert resultado == {"aplicadas": 2}
    assert db.query(ConceptoAdicional).count() == 2
    assert {c.linea_id for c in db.query(ConceptoAdicional).all()} == {l1.id, l2.id}


def test_masivo_primer_id_inexistente_da_no_existe_el_codigo(db):
    """Si linea_ids[0] no existe, la quincena queda en None y la búsqueda de
    la regla no encuentra nada: sale "No existe el código", aunque el código
    SÍ existe en el maestro de la quincena de las otras líneas. El mensaje es
    engañoso, pero es el contrato actual (el endpoint lo devuelve como 404)."""
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="No existe el código 461 en el maestro de esta quincena"):
        svc.agregar_concepto_masivo([999, l1.id, l2.id], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_masivo_codigo_sin_regla_en_la_quincena(db):
    """El código existe, pero en el maestro de OTRA quincena: no vale."""
    preliq = _preliq(db, quincena=Q1)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db, quincena=Q2, codigo=461)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="No existe el código 461 en el maestro de esta quincena"):
        svc.agregar_concepto_masivo([l1.id, l2.id], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0
    db.expire_all()
    assert db.get(PreliquidacionLinea, l1.id).importe_total == Decimal("0")


# ─── eliminar_concepto_masivo ─────────────────────────────────────────────────

def test_eliminar_masivo_borra_solo_ese_codigo_en_esas_lineas(db):
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)
    _concepto_existente(db, l1, "800.00", codigo=461)
    _concepto_existente(db, l1, "200.00", codigo=500)
    _concepto_existente(db, l2, "400.00", codigo=461)
    _concepto_existente(db, l3, "300.00", codigo=461)  # fuera de la selección
    svc = PreliquidacionService(db)

    resultado = svc.eliminar_concepto_masivo([l1.id, l2.id], 461)

    assert resultado == {"eliminados": 2, "lineas": 2}
    db.expire_all()
    linea1 = db.get(PreliquidacionLinea, l1.id)
    assert [c.codigo_concepto for c in linea1.conceptos] == [500]
    assert linea1.importe_total == Decimal("200.00")
    linea2 = db.get(PreliquidacionLinea, l2.id)
    assert linea2.conceptos == []
    assert linea2.importe_total == Decimal("0")
    linea3 = db.get(PreliquidacionLinea, l3.id)
    assert [c.codigo_concepto for c in linea3.conceptos] == [461]
    assert linea3.importe_total == Decimal("300.00")


def test_eliminar_masivo_lista_vacia_no_toca_la_base(db):
    preliq = _preliq(db)
    l1, _, _ = _tres_lineas(db, preliq)
    _concepto_existente(db, l1, "800.00", codigo=461)
    svc = PreliquidacionService(db)

    assert svc.eliminar_concepto_masivo([], 461) == {"eliminados": 0, "lineas": 0}
    assert db.query(ConceptoAdicional).count() == 1
    db.expire_all()
    assert db.get(PreliquidacionLinea, l1.id).importe_total == Decimal("800.00")


# ─── Endpoints ────────────────────────────────────────────────────────────────

def test_endpoint_agregar_sin_linea_ids_da_400(cliente, db):
    r = cliente.post(URL_AGREGAR, json={"linea_ids": [], "codigo": 461})
    assert r.status_code == 400
    assert r.json()["detail"] == "Se requieren linea_ids y codigo"


def test_endpoint_agregar_valido_da_200(cliente, db):
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db)

    r = cliente.post(URL_AGREGAR, json={"linea_ids": [l1.id, l2.id], "codigo": 461})

    assert r.status_code == 200
    assert r.json()["mensaje"] == "Concepto agregado"
    assert r.json()["detalle"] == "2 líneas actualizadas"
    conceptos = db.query(ConceptoAdicional).all()
    assert {c.linea_id for c in conceptos} == {l1.id, l2.id}
    assert {c.ingresado_por for c in conceptos} == {USUARIO}


def test_endpoint_agregar_codigo_inexistente_da_404(cliente, db):
    preliq = _preliq(db)
    l1, _, _ = _tres_lineas(db, preliq)
    _regla(db, codigo=461)

    r = cliente.post(URL_AGREGAR, json={"linea_ids": [l1.id], "codigo": 999})

    assert r.status_code == 404
    assert r.json()["detail"] == "No existe el código 999 en el maestro de esta quincena"
    assert db.query(ConceptoAdicional).count() == 0


def test_endpoint_eliminar_sin_linea_ids_da_400(cliente, db):
    r = cliente.post(URL_ELIMINAR, json={"linea_ids": [], "codigo": 461})
    assert r.status_code == 400
    assert r.json()["detail"] == "Se requieren linea_ids y codigo"


def test_endpoint_eliminar_valido_da_200(cliente, db):
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _concepto_existente(db, l1, "800.00", codigo=461)
    _concepto_existente(db, l2, "400.00", codigo=461)

    r = cliente.post(URL_ELIMINAR, json={"linea_ids": [l1.id, l2.id], "codigo": 461})

    assert r.status_code == 200
    assert r.json()["mensaje"] == "Concepto eliminado"
    assert r.json()["detalle"] == "2 conceptos eliminados de 2 líneas"
    assert db.query(ConceptoAdicional).count() == 0
