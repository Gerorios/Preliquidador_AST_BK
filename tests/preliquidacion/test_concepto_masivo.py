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
from app.modulos.preliquidacion.services.preliquidacion_service import (
    ExtraCodigoRepetido, ExtraRequiereOpcion, PreliquidacionService,
)

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
           unidad=UnidadBaseConcepto.HSJORNAL, tarea="TAREA X"):
    r = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, codigo=codigo,
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

    assert resultado == {"aplicadas": 3, "salteadas": 0}
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
        assert c.descripcion == "Concepto 461 (extra, de TAREA X)"
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

    assert resultado == {"aplicadas": 2, "salteadas": 0}
    assert db.query(ConceptoAdicional).count() == 2
    assert {c.linea_id for c in db.query(ConceptoAdicional).all()} == {l1.id, l2.id}


def test_masivo_primer_id_inexistente_usa_la_quincena_de_las_que_existen(db):
    """Si linea_ids[0] no existe, la quincena sale de las líneas que sí
    existen: el código se encuentra y se aplica a esas dos."""
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo([999, l1.id, l2.id], 461, USUARIO)

    assert resultado == {"aplicadas": 2, "salteadas": 0}
    assert {c.linea_id for c in db.query(ConceptoAdicional).all()} == {l1.id, l2.id}


def test_masivo_sin_lineas_da_valueerror(db):
    preliq = _preliq(db)
    _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="Se requieren linea_ids"):
        svc.agregar_concepto_masivo([], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_masivo_ningun_id_existe(db):
    preliq = _preliq(db)
    _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="Ninguna de las líneas indicadas existe"):
        svc.agregar_concepto_masivo([998, 999], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_masivo_lineas_de_dos_quincenas(db):
    p1 = _preliq(db, quincena=Q1)
    p2 = _preliq(db, quincena=Q2)
    l1 = _linea(db, p1)
    l2 = _linea(db, p2, nombre_empleado="PERSONA DOS", cuit="20000000002",
                legajo_campo="0002", legajo_asignado="0002")
    _regla(db, quincena=Q1)
    _regla(db, quincena=Q2)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="Las líneas indicadas pertenecen a más de una quincena"):
        svc.agregar_concepto_masivo([l1.id, l2.id], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0
    db.expire_all()
    assert db.get(PreliquidacionLinea, l1.id).importe_total == Decimal("0")
    assert db.get(PreliquidacionLinea, l2.id).importe_total == Decimal("0")


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


def test_masivo_regla_sin_precio_no_escribe_nada(db):
    """La única regla del código no tiene precio: no hay opción elegible y
    no se escribe nada en ninguna línea (ADR-0015, sin escritura parcial)."""
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)
    _regla(db, precio=None)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="no tiene precio cargado"):
        svc.agregar_concepto_masivo([l1.id, l2.id, l3.id], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0
    db.expire_all()
    for linea_id in (l1.id, l2.id, l3.id):
        assert db.get(PreliquidacionLinea, linea_id).importe_total == Decimal("0")


def test_masivo_dos_opciones_sin_elegir_no_escribe_nada(db):
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)
    _regla(db, precio=Decimal("1000.00"), unidad=UnidadBaseConcepto.HSJORNAL)
    _regla(db, precio=Decimal("3000.00"), unidad=UnidadBaseConcepto.JORNAL_TOPE1,
           tarea="TAREA Y")
    svc = PreliquidacionService(db)

    with pytest.raises(ExtraRequiereOpcion):
        svc.agregar_concepto_masivo([l1.id, l2.id, l3.id], 461, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0
    db.expire_all()
    for linea_id in (l1.id, l2.id, l3.id):
        assert db.get(PreliquidacionLinea, linea_id).importe_total == Decimal("0")


def test_masivo_con_opcion_una_regla_y_cantidad_por_linea(db):
    """Opción (3000, jornal_tope1) elegida entre dos: todas las líneas quedan
    atadas a la misma regla (la representante de la opción) y la cantidad se
    calcula por línea con sus horas."""
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)  # 8 / 4 / 2.5 hs
    _concepto_existente(db, l1, "100.00")
    _regla(db, precio=Decimal("1000.00"), unidad=UnidadBaseConcepto.HSJORNAL,
           tarea="TAREA 0")
    _regla(db, precio=Decimal("3000.00"), unidad=UnidadBaseConcepto.JORNAL_TOPE1,
           tarea="TAREA B")
    representante = _regla(db, precio=Decimal("3000.00"),
                           unidad=UnidadBaseConcepto.JORNAL_TOPE1, tarea="TAREA A")
    svc = PreliquidacionService(db)
    opcion = {"precio": "3000", "unidad_base": "jornal_tope1", "tipo": "REMUNERATIVO"}

    resultado = svc.agregar_concepto_masivo(
        [l1.id, l2.id, l3.id], 461, USUARIO, opcion=opcion,
    )

    assert resultado == {"aplicadas": 3, "salteadas": 0}
    db.expire_all()
    esperado = {  # linea_id: (cantidad, importe del extra, importe_total)
        l1.id: (Decimal("1"), Decimal("3000.00"), Decimal("3100.00")),
        l2.id: (Decimal("0.5"), Decimal("1500.00"), Decimal("1500.00")),
        l3.id: (Decimal("0.5"), Decimal("1500.00"), Decimal("1500.00")),
    }
    for linea_id, (cantidad, importe, total) in esperado.items():
        linea = db.get(PreliquidacionLinea, linea_id)
        extras = [c for c in linea.conceptos if c.codigo_concepto == 461]
        assert len(extras) == 1
        c = extras[0]
        assert c.cantidad == cantidad
        assert c.importe == importe
        assert c.precio == Decimal("3000.00")
        assert c.unidad_base == "jornal_tope1"
        assert c.concepto_liquidacion_id == representante.id
        assert c.descripcion == "Concepto 461 (extra, de TAREA A)"
        assert c.ingresado_por == USUARIO
        assert linea.importe_total == total


def _con_461_en_l1_y_l2(db):
    """l1 tiene el 461 automático (800), l2 lo tiene como extra (400) y l3
    no lo tiene. Una sola regla 461 (1000, hsjornal)."""
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)  # 8 / 4 / 2.5 hs
    _concepto_existente(db, l1, "800.00", codigo=461)
    extra = _concepto_existente(db, l2, "400.00", codigo=461)
    extra.ingresado_por = USUARIO
    db.commit()
    _regla(db, precio=Decimal("1000.00"))
    return l1, l2, l3


def test_masivo_repetido_frenar_no_escribe_nada(db):
    l1, l2, l3 = _con_461_en_l1_y_l2(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ExtraCodigoRepetido) as exc:
        svc.agregar_concepto_masivo([l1.id, l2.id, l3.id], 461, USUARIO)

    detalle = exc.value.detalle
    assert detalle["tipo"] == "codigo_repetido"
    assert detalle["codigo"] == 461
    assert detalle["lineas_con_codigo"] == 2
    assert detalle["total_lineas"] == 3
    assert detalle["mensaje"] == "2 de las 3 líneas ya tienen el código 461."
    assert db.query(ConceptoAdicional).count() == 2
    db.expire_all()
    assert db.get(PreliquidacionLinea, l1.id).importe_total == Decimal("800.00")
    assert db.get(PreliquidacionLinea, l2.id).importe_total == Decimal("400.00")
    assert db.get(PreliquidacionLinea, l3.id).importe_total == Decimal("0")


def test_masivo_repetido_frenar_es_el_default_y_explicito_igual(db):
    l1, l2, l3 = _con_461_en_l1_y_l2(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ExtraCodigoRepetido):
        svc.agregar_concepto_masivo(
            [l1.id, l2.id, l3.id], 461, USUARIO, si_repetido="frenar",
        )
    assert db.query(ConceptoAdicional).count() == 2


def test_masivo_repetido_saltear_agrega_solo_a_las_que_no_lo_tienen(db):
    l1, l2, l3 = _con_461_en_l1_y_l2(db)
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo(
        [l1.id, l2.id, l3.id], 461, USUARIO, si_repetido="saltear",
    )

    assert resultado == {"aplicadas": 1, "salteadas": 2}
    assert db.query(ConceptoAdicional).count() == 3
    db.expire_all()
    linea1 = db.get(PreliquidacionLinea, l1.id)
    assert len(linea1.conceptos) == 1
    assert linea1.importe_total == Decimal("800.00")
    linea2 = db.get(PreliquidacionLinea, l2.id)
    assert len(linea2.conceptos) == 1
    assert linea2.importe_total == Decimal("400.00")
    linea3 = db.get(PreliquidacionLinea, l3.id)
    assert len(linea3.conceptos) == 1
    c = linea3.conceptos[0]
    assert c.codigo_concepto == 461
    assert c.ingresado_por == USUARIO
    assert c.importe == Decimal("2500.00")  # 2.5 hs × 1000
    assert linea3.importe_total == Decimal("2500.00")


def test_masivo_repetido_agregar_agrega_a_todas_y_suma(db):
    l1, l2, l3 = _con_461_en_l1_y_l2(db)
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo(
        [l1.id, l2.id, l3.id], 461, USUARIO, si_repetido="agregar",
    )

    assert resultado == {"aplicadas": 3, "salteadas": 0}
    assert db.query(ConceptoAdicional).count() == 5
    db.expire_all()
    linea1 = db.get(PreliquidacionLinea, l1.id)
    importes1 = sorted(c.importe for c in linea1.conceptos if c.codigo_concepto == 461)
    assert importes1 == [Decimal("800.00"), Decimal("8000.00")]
    assert linea1.importe_total == Decimal("8800.00")  # 800 previo + 8 × 1000
    linea2 = db.get(PreliquidacionLinea, l2.id)
    assert len([c for c in linea2.conceptos if c.codigo_concepto == 461]) == 2
    assert linea2.importe_total == Decimal("4400.00")  # 400 previo + 4 × 1000
    assert db.get(PreliquidacionLinea, l3.id).importe_total == Decimal("2500.00")


@pytest.mark.parametrize("modo", ["frenar", "saltear", "agregar"])
def test_masivo_sin_repetidos_cualquier_modo_agrega_a_todas(db, modo):
    """Un manual libre (sin código) no cuenta como repetido."""
    preliq = _preliq(db)
    l1, l2, l3 = _tres_lineas(db, preliq)
    manual = _concepto_existente(db, l1, "100.00")  # codigo=None
    manual.ingresado_por = USUARIO
    db.commit()
    _regla(db, precio=Decimal("1000.00"))
    svc = PreliquidacionService(db)

    resultado = svc.agregar_concepto_masivo(
        [l1.id, l2.id, l3.id], 461, USUARIO, si_repetido=modo,
    )

    assert resultado == {"aplicadas": 3, "salteadas": 0}
    db.expire_all()
    assert db.get(PreliquidacionLinea, l1.id).importe_total == Decimal("8100.00")
    assert db.get(PreliquidacionLinea, l2.id).importe_total == Decimal("4000.00")
    assert db.get(PreliquidacionLinea, l3.id).importe_total == Decimal("2500.00")


def test_masivo_si_repetido_invalido_da_valueerror_sin_escribir(db):
    preliq = _preliq(db)
    l1, l2, _ = _tres_lineas(db, preliq)
    _regla(db)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="si_repetido"):
        svc.agregar_concepto_masivo([l1.id, l2.id], 461, USUARIO, si_repetido="otra")
    assert db.query(ConceptoAdicional).count() == 0


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
