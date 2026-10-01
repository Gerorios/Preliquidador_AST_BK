"""Concepto extra (ADR-0015): el extra sigue al maestro.

B1: planificar_extras decide, sin escribir, qué pasa con cada extra atado a
las reglas tocadas: reatar a otra regla con su opción, seguir a su regla o
borrarse. B2: aplicar_plan_extras lo escribe en la sesión, sin commit. B3 y
B4: el PATCH y el DELETE del maestro lo aplican, con el 409 borra_extras. B5:
el precio masivo lo aplica; nunca borra, y si tuviera que borrar un extra viejo
frena con el 409 extras_a_revisar. B6: tests documentales de lo que no
cambia (regla nueva, extra que no vuelve, manual libre).
SQLite en memoria; todos los datos son ficticios.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.api.precios import (
    actualizar_concepto, crear_concepto, eliminar_concepto, precio_masivo,
)
from app.modulos.preliquidacion.models import (
    ConceptoAdicional, ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea,
    TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.schemas import (
    ConceptoPrecioMasivoRequest, ConceptoUnifRequest, ConceptoUnifUpdateRequest,
)
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
CODIGO = 902
USUARIO = 7
OPCION_1000 = {"precio": "1000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO"}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _regla(db, tarea, precio=Decimal("1000"), unidad=UnidadBaseConcepto.HSJORNAL,
           tipo=TipoConcepto.REMUNERATIVO, quincena=Q1, codigo=CODIGO, **extra):
    r = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, codigo=codigo,
        unidad_base=unidad, precio=precio, tipo=tipo, **extra,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _linea(db, preliq, tarea, **extra):
    datos = dict(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit="20000000001", nombre_empleado="PERSONA UNO", legajo_campo="0001",
        empresa_asignada="LA ASTURIANA", legajo_asignado="0001",
        fecha_tarea=date(2026, 5, 2),
        # El modelo trae linea_incompleta=True por default: se apaga explícito.
        es_duplicado=False, alerta_legajo=False, alerta_empresa=False, linea_incompleta=False,
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    datos.update(extra)
    linea = PreliquidacionLinea(**datos)
    db.add(linea)
    db.commit()
    db.refresh(linea)
    return linea


def _escenario(db, con_b=True):
    """Fixture base de la etapa B (plan §5).

    A (TAREA A) y B (TAREA B): 902, 1000, hsjornal, REMUNERATIVO. C (TAREA C):
    902, 5000, fijo. Línea Y (TAREA Z, 8 hs) con 100 previos (un manual libre)
    y un extra 1000/hsjornal atado a A. Línea X (TAREA A) con el automático de
    A. `con_b=False` es la variante sin B.
    """
    a = _regla(db, "TAREA A")
    b = _regla(db, "TAREA B") if con_b else None
    c = _regla(db, "TAREA C", precio=Decimal("5000"), unidad=UnidadBaseConcepto.FIJO)

    preliq = Preliquidacion(quincena=Q1, creado_por=1)
    db.add(preliq)
    db.commit()

    y = _linea(db, preliq, "TAREA Z")
    manual = ConceptoAdicional(
        linea_id=y.id, descripcion="Plus a mano", importe=Decimal("100.00"),
        tipo=TipoConcepto.OTRO, ingresado_por=USUARIO,
    )
    db.add(manual)
    y.importe_total = Decimal("100.00")
    db.commit()

    x = _linea(db, preliq, "TAREA A", nombre_empleado="PERSONA DOS", cuit="20000000002")
    svc = PreliquidacionService(db)
    automatico = svc._generar_conceptos_automaticos(x, [a])[0]
    db.add(automatico)
    x.importe_total = automatico.importe
    db.commit()

    extra = svc.agregar_concepto_por_codigo(y.id, CODIGO, USUARIO, opcion=OPCION_1000)
    assert extra.concepto_liquidacion_id == a.id  # TAREA A va primero
    assert extra.importe == Decimal("8000.00")

    return SimpleNamespace(
        svc=svc, a=a, b=b, c=c, y=y, x=x, manual=manual,
        automatico=automatico, extra=extra,
    )


def _reatados(plan):
    return [(extra.id, regla.id) for extra, regla in plan.reatar]


def _ids(conceptos):
    return [c.id for c in conceptos]


def _vacio(plan):
    return not plan.reatar and not plan.seguir and not plan.borrar


# ─── 1. Sin cambio ───────────────────────────────────────────────────────────

def test_regla_intacta_plan_vacio(db):
    e = _escenario(db)

    plan = e.svc.planificar_extras([e.a.id])

    assert _vacio(plan)


def test_campo_irrelevante_reemplaza_comun_plan_vacio(db):
    e = _escenario(db)
    e.a.reemplaza_comun = True
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert _vacio(plan)


def test_solo_entran_los_extras_atados_a_las_reglas_dadas(db):
    # El extra está atado a A: cambiar B o C (aunque C pase a la opción del
    # extra) no lo planifica.
    e = _escenario(db)
    e.a.precio = Decimal("1200")
    e.c.precio = Decimal("1000")
    e.c.unidad_base = UnidadBaseConcepto.HSJORNAL
    db.flush()

    plan = e.svc.planificar_extras([e.b.id, e.c.id])

    assert _vacio(plan)


# ─── 2. Reatar ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cambio", [
    {"precio": Decimal("1200")},
    {"unidad_base": UnidadBaseConcepto.FIJO},
    {"tipo": TipoConcepto.NO_REMUNERATIVO},
    {"codigo": 903},
    {"precio": None},
    {"codigo": None},
    {"categoria": 3},
], ids=["precio", "unidad", "tipo", "codigo", "sin_precio", "sin_codigo", "categoria"])
def test_con_otra_regla_que_ofrece_la_opcion_se_reata(db, cambio):
    e = _escenario(db)
    for campo, valor in cambio.items():
        setattr(e.a, campo, valor)
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert _reatados(plan) == [(e.extra.id, e.b.id)]
    assert plan.seguir == []
    assert plan.borrar == []


def test_reata_a_la_representante_de_las_que_ofrecen_la_opcion(db):
    e = _escenario(db)
    # "TAREA AB" va antes que "TAREA B" por orden alfabético.
    ab = _regla(db, "TAREA AB")
    e.a.precio = Decimal("1200")
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert _reatados(plan) == [(e.extra.id, ab.id)]


def test_regla_excluida_con_b_se_reata(db):
    e = _escenario(db)

    plan = e.svc.planificar_extras([e.a.id], excluir_ids={e.a.id})

    assert _reatados(plan) == [(e.extra.id, e.b.id)]
    assert plan.seguir == []
    assert plan.borrar == []


def test_no_reata_a_una_regla_excluida(db):
    e = _escenario(db)
    e.a.precio = Decimal("1200")
    db.flush()

    plan = e.svc.planificar_extras([e.a.id], excluir_ids={e.b.id})

    assert plan.reatar == []
    assert _ids(plan.seguir) == [e.extra.id]


def test_no_reata_a_otra_quincena_ni_a_una_regla_con_categoria(db):
    e = _escenario(db, con_b=False)
    _regla(db, "TAREA B", quincena=Q2)
    _regla(db, "TAREA B", categoria=4)
    e.a.precio = Decimal("1200")
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert plan.reatar == []
    assert _ids(plan.seguir) == [e.extra.id]


def test_regla_borrada_de_la_sesion_con_b_se_reata(db):
    # SQLite sin PRAGMA foreign_keys: el SET NULL no corre y el extra conserva
    # el id de A, que ya no existe.
    e = _escenario(db)
    a_id = e.a.id
    db.delete(e.a)
    db.flush()

    plan = e.svc.planificar_extras([a_id])

    assert _reatados(plan) == [(e.extra.id, e.b.id)]


# ─── 3. Seguir ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cambio", [
    {"precio": Decimal("1200")},
    {"unidad_base": UnidadBaseConcepto.FIJO},
    {"tipo": TipoConcepto.NO_REMUNERATIVO},
    {"codigo": 903},
], ids=["precio", "unidad", "tipo", "codigo"])
def test_sin_otra_regla_con_la_opcion_sigue_a_su_regla(db, cambio):
    e = _escenario(db, con_b=False)
    for campo, valor in cambio.items():
        setattr(e.a, campo, valor)
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert plan.reatar == []
    assert _ids(plan.seguir) == [e.extra.id]
    assert plan.borrar == []


# ─── 4. Borrar ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cambio", [
    {"precio": None},
    {"codigo": None},
    {"categoria": 3},
], ids=["sin_precio", "sin_codigo", "categoria"])
def test_sin_otra_regla_y_regla_inelegible_se_borra(db, cambio):
    # Sin precio o sin código: reglas viejas (ADR-0016 ya no deja guardarlas
    # así), seteadas por ORM. Con categoría: plan §7, pregunta 1.
    e = _escenario(db, con_b=False)
    for campo, valor in cambio.items():
        setattr(e.a, campo, valor)
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert plan.reatar == []
    assert plan.seguir == []
    assert _ids(plan.borrar) == [e.extra.id]


def test_regla_excluida_sin_b_se_borra(db):
    e = _escenario(db, con_b=False)

    plan = e.svc.planificar_extras([e.a.id], excluir_ids={e.a.id})

    assert plan.reatar == []
    assert plan.seguir == []
    assert _ids(plan.borrar) == [e.extra.id]


def test_regla_borrada_de_la_sesion_sin_b_se_borra(db):
    e = _escenario(db, con_b=False)
    a_id = e.a.id
    db.delete(e.a)
    db.flush()

    plan = e.svc.planificar_extras([a_id])

    assert plan.reatar == []
    assert plan.seguir == []
    assert _ids(plan.borrar) == [e.extra.id]


# ─── Manual libre, automático y sin escritura ────────────────────────────────

@pytest.mark.parametrize("con_b", [True, False], ids=["con_b", "sin_b"])
def test_manual_libre_y_automatico_nunca_aparecen(db, con_b):
    e = _escenario(db, con_b=con_b)
    e.a.precio = None
    db.flush()

    plan = e.svc.planificar_extras([e.a.id], excluir_ids={e.a.id})

    planificados = [extra.id for extra, _ in plan.reatar] + _ids(plan.seguir) + _ids(plan.borrar)
    assert planificados == [e.extra.id]
    assert e.manual.id not in planificados
    assert e.automatico.id not in planificados


def test_planificar_no_escribe(db):
    e = _escenario(db, con_b=False)
    total_conceptos = db.query(ConceptoAdicional).count()
    e.a.precio = None
    db.flush()

    plan = e.svc.planificar_extras([e.a.id])

    assert _ids(plan.borrar) == [e.extra.id]
    # Nada pendiente en la sesión y el extra intacto en memoria.
    assert not db.new and not db.dirty and not db.deleted
    assert e.extra.concepto_liquidacion_id == e.a.id
    assert e.extra.importe == Decimal("8000.00")
    assert db.query(ConceptoAdicional).count() == total_conceptos

    # Y nada se commiteó: el rollback deja todo como estaba antes del cambio.
    db.rollback()
    db.expire_all()
    extra = db.get(ConceptoAdicional, e.extra.id)
    assert extra.concepto_liquidacion_id == e.a.id
    assert extra.precio == Decimal("1000")
    assert extra.importe == Decimal("8000.00")
    assert extra.descripcion == "Concepto 902 (extra, de TAREA A)"
    assert db.get(ConceptoLiquidacion, e.a.id).precio == Decimal("1000")
    assert db.get(PreliquidacionLinea, e.y.id).importe_total == Decimal("8100.00")
    assert db.query(ConceptoAdicional).count() == total_conceptos


def test_lista_de_reglas_vacia_plan_vacio(db):
    e = _escenario(db)

    assert _vacio(e.svc.planificar_extras([]))


# ─── B2. aplicar_plan_extras ─────────────────────────────────────────────────
# Escribe en la sesión sin commit (el que llama commitea) y recalcula el
# importe_total de las líneas afectadas. Línea Y: 8 hs, 100 previos.

def _planificar_y_aplicar(e, db, cambio, excluir_ids=()):
    for campo, valor in cambio.items():
        setattr(e.a, campo, valor)
    db.flush()
    plan = e.svc.planificar_extras([e.a.id], excluir_ids=excluir_ids)
    return e.svc.aplicar_plan_extras(plan)


def test_aplicar_reatar_cambia_regla_y_descripcion_sin_tocar_importe(db):
    e = _escenario(db)

    conteos = _planificar_y_aplicar(e, db, {"precio": Decimal("1200")})

    assert conteos == {"reatados": 1, "seguidos": 0, "borrados": 0, "lineas": 1}
    assert e.extra.concepto_liquidacion_id == e.b.id
    assert e.extra.descripcion == "Concepto 902 (extra, de TAREA B)"
    # La opción guardada y el importe quedan igual.
    assert e.extra.precio == Decimal("1000")
    assert e.extra.unidad_base == "hsjornal"
    assert e.extra.tipo == TipoConcepto.REMUNERATIVO
    assert e.extra.cantidad == Decimal("8")
    assert e.extra.importe == Decimal("8000.00")
    assert e.y.importe_total == Decimal("8100.00")


def test_aplicar_seguir_precio_recalcula_importe_y_total(db):
    e = _escenario(db, con_b=False)

    conteos = _planificar_y_aplicar(e, db, {"precio": Decimal("1200")})

    assert conteos == {"reatados": 0, "seguidos": 1, "borrados": 0, "lineas": 1}
    assert e.extra.concepto_liquidacion_id == e.a.id
    assert e.extra.precio == Decimal("1200")
    assert e.extra.importe == Decimal("9600.00")
    assert e.extra.descripcion == "Concepto 902 (extra, de TAREA A)"
    assert e.y.importe_total == Decimal("9700.00")
    # El automático de X no es asunto de aplicar_plan_extras.
    assert e.x.importe_total == Decimal("8000.00")


def test_aplicar_seguir_unidad_fijo(db):
    e = _escenario(db, con_b=False)

    _planificar_y_aplicar(e, db, {"unidad_base": UnidadBaseConcepto.FIJO})

    assert e.extra.unidad_base == "fijo"
    assert isinstance(e.extra.unidad_base, str)
    assert e.extra.cantidad == Decimal("1")
    assert e.extra.importe == Decimal("1000.00")
    assert e.y.importe_total == Decimal("1100.00")


def test_aplicar_seguir_codigo(db):
    e = _escenario(db, con_b=False)

    _planificar_y_aplicar(e, db, {"codigo": 903})

    assert e.extra.codigo_concepto == 903
    assert e.extra.descripcion == "Concepto 903 (extra, de TAREA A)"
    assert e.extra.importe == Decimal("8000.00")
    assert e.y.importe_total == Decimal("8100.00")


def test_aplicar_seguir_tipo(db):
    e = _escenario(db, con_b=False)

    _planificar_y_aplicar(e, db, {"tipo": TipoConcepto.NO_REMUNERATIVO})

    assert e.extra.tipo == TipoConcepto.NO_REMUNERATIVO
    assert e.extra.importe == Decimal("8000.00")


def test_aplicar_borrar_saca_el_extra_y_recalcula_total(db):
    e = _escenario(db, con_b=False)
    extra_id = e.extra.id

    conteos = _planificar_y_aplicar(e, db, {"categoria": 3})

    assert conteos == {"reatados": 0, "seguidos": 0, "borrados": 1, "lineas": 1}
    assert db.get(ConceptoAdicional, extra_id) is None
    assert extra_id not in _ids(e.y.conceptos)
    assert e.y.importe_total == Decimal("100.00")


def test_aplicar_borrar_con_la_coleccion_ya_cargada(db):
    # Si linea.conceptos ya estaba en memoria antes de aplicar, el total no
    # puede contar al extra borrado.
    e = _escenario(db, con_b=False)
    extra_id = e.extra.id
    assert extra_id in _ids(e.y.conceptos)

    _planificar_y_aplicar(e, db, {"categoria": 3})

    assert extra_id not in _ids(e.y.conceptos)
    assert e.y.importe_total == Decimal("100.00")


def test_aplicar_dos_extras_en_la_misma_linea(db):
    e = _escenario(db, con_b=False)
    otro = e.svc.agregar_concepto_por_codigo(
        e.y.id, CODIGO, USUARIO, opcion=OPCION_1000, confirmar_repetido=True,
    )
    assert e.y.importe_total == Decimal("16100.00")

    conteos = _planificar_y_aplicar(e, db, {"precio": Decimal("1200")})

    assert conteos == {"reatados": 0, "seguidos": 2, "borrados": 0, "lineas": 1}
    assert e.extra.importe == Decimal("9600.00")
    assert otro.importe == Decimal("9600.00")
    assert e.y.importe_total == Decimal("19300.00")


def test_aplicar_no_commitea(db):
    e = _escenario(db, con_b=False)

    _planificar_y_aplicar(e, db, {"precio": Decimal("1200")})
    db.rollback()
    db.expire_all()

    extra = db.get(ConceptoAdicional, e.extra.id)
    assert extra.importe == Decimal("8000.00")
    assert db.get(PreliquidacionLinea, e.y.id).importe_total == Decimal("8100.00")


@pytest.mark.parametrize("con_b,cambio", [
    (True, {"precio": Decimal("1200")}),
    (False, {"precio": Decimal("1200")}),
    (False, {"categoria": 3}),
], ids=["reatar", "seguir", "borrar"])
def test_aplicar_y_commitear_persiste(db, con_b, cambio):
    e = _escenario(db, con_b=con_b)
    extra_id, y_id = e.extra.id, e.y.id
    esperado_regla = e.b.id if con_b else e.a.id

    _planificar_y_aplicar(e, db, cambio)
    db.commit()
    db.expire_all()

    extra = db.query(ConceptoAdicional).filter(ConceptoAdicional.id == extra_id).first()
    total = db.query(PreliquidacionLinea.importe_total).filter(
        PreliquidacionLinea.id == y_id,
    ).scalar()
    if "categoria" in cambio:
        assert extra is None
        assert total == Decimal("100.00")
    elif con_b:
        assert extra.concepto_liquidacion_id == esperado_regla
        assert extra.descripcion == "Concepto 902 (extra, de TAREA B)"
        assert extra.importe == Decimal("8000.00")
        assert total == Decimal("8100.00")
    else:
        assert extra.concepto_liquidacion_id == esperado_regla
        assert extra.precio == Decimal("1200")
        assert extra.importe == Decimal("9600.00")
        assert total == Decimal("9700.00")


# ─── B3. PATCH /conceptos/{id} ───────────────────────────────────────────────
# Se llama la función del endpoint directo, como test_copiar_heredado.py. La
# fixture tiene Preliquidacion de Q1, así que recalcular_por_concepto actúa
# sobre la línea X (TAREA A). La línea Y (TAREA Z) sólo la toca el plan.

def _patch(e, db, confirmar_borrado_extras=None, **campos):
    kwargs = {}
    if confirmar_borrado_extras is not None:
        kwargs["confirmar_borrado_extras"] = confirmar_borrado_extras
    return actualizar_concepto(
        concepto_id=e.a.id, datos=ConceptoUnifUpdateRequest(**campos), db=db, **kwargs,
    )


def _desde_la_base(db, e):
    """Relee de la base el extra, los totales de Y y X y la regla A."""
    db.expire_all()
    extra = db.query(ConceptoAdicional).filter(ConceptoAdicional.id == e.extra.id).first()
    total_y = db.query(PreliquidacionLinea.importe_total).filter(
        PreliquidacionLinea.id == e.y.id).scalar()
    total_x = db.query(PreliquidacionLinea.importe_total).filter(
        PreliquidacionLinea.id == e.x.id).scalar()
    regla_a = db.query(ConceptoLiquidacion).filter(ConceptoLiquidacion.id == e.a.id).first()
    return SimpleNamespace(extra=extra, total_y=total_y, total_x=total_x, a=regla_a)


def test_patch_precio_con_b_reata_y_recalcula_x(db):
    e = _escenario(db)

    _patch(e, db, precio=Decimal("1200"))

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.b.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA B)"
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")
    assert r.total_x == Decimal("9600.00")
    assert r.a.heredado is False


def test_patch_precio_sin_b_el_extra_sigue(db):
    e = _escenario(db, con_b=False)

    _patch(e, db, precio=Decimal("1200"))

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.precio == Decimal("1200")
    assert r.extra.importe == Decimal("9600.00")
    assert r.total_y == Decimal("9700.00")
    assert r.total_x == Decimal("9600.00")


def test_patch_codigo_sin_b_el_extra_sigue(db):
    e = _escenario(db, con_b=False)

    _patch(e, db, codigo=903)

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.codigo_concepto == 903
    assert r.extra.descripcion == "Concepto 903 (extra, de TAREA A)"
    assert r.total_y == Decimal("8100.00")


def test_patch_categoria_sin_b_sin_flag_409_y_no_cambia_nada(db):
    e = _escenario(db, con_b=False)

    with pytest.raises(HTTPException) as exc:
        _patch(e, db, categoria=3)

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "tipo": "borra_extras",
        "mensaje": "Esta acción borra 1 concepto(s) extra en 1 línea(s) de Revisión.",
        "extras": 1,
        "lineas": 1,
    }
    r = _desde_la_base(db, e)
    assert r.a.categoria is None
    assert r.extra is not None
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")
    assert r.total_x == Decimal("8000.00")


def test_patch_categoria_sin_b_con_flag_borra_el_extra(db):
    e = _escenario(db, con_b=False)

    _patch(e, db, categoria=3, confirmar_borrado_extras=True)

    r = _desde_la_base(db, e)
    assert r.a.categoria == 3
    assert r.extra is None
    assert r.total_y == Decimal("100.00")


def test_patch_categoria_con_b_reata_sin_409(db):
    e = _escenario(db)

    _patch(e, db, categoria=3)

    r = _desde_la_base(db, e)
    assert r.a.categoria == 3
    assert r.extra.concepto_liquidacion_id == e.b.id
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")


@pytest.mark.parametrize("campo", ["precio", "codigo"])
def test_patch_null_sigue_dando_422_y_no_toca_el_extra(db, campo):
    # Regresión ADR-0016: el schema rechaza (422) antes de llegar al endpoint.
    e = _escenario(db, con_b=False)

    with pytest.raises(ValidationError):
        ConceptoUnifUpdateRequest(**{campo: None})

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")


# ─── B4. DELETE /conceptos/{id} ──────────────────────────────────────────────
# El plan va con excluir_ids={id} y se aplica ANTES del delete: la FK del
# extra es ON DELETE SET NULL, y si el delete fuera primero el extra quedaría
# sin regla.

def _delete(e, db, concepto_id=None, confirmar_borrado_extras=None):
    kwargs = {}
    if confirmar_borrado_extras is not None:
        kwargs["confirmar_borrado_extras"] = confirmar_borrado_extras
    return eliminar_concepto(
        concepto_id=e.a.id if concepto_id is None else concepto_id, db=db, **kwargs,
    )


def test_delete_sin_b_sin_flag_409_y_no_cambia_nada(db):
    e = _escenario(db, con_b=False)

    with pytest.raises(HTTPException) as exc:
        _delete(e, db)

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "tipo": "borra_extras",
        "mensaje": "Esta acción borra 1 concepto(s) extra en 1 línea(s) de Revisión.",
        "extras": 1,
        "lineas": 1,
    }
    r = _desde_la_base(db, e)
    assert r.a is not None
    assert r.extra is not None
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")
    assert r.total_x == Decimal("8000.00")


def test_delete_sin_b_con_flag_borra_regla_y_extra(db):
    e = _escenario(db, con_b=False)

    respuesta = _delete(e, db, confirmar_borrado_extras=True)

    assert respuesta.mensaje == "Concepto eliminado"
    r = _desde_la_base(db, e)
    assert r.a is None
    assert r.extra is None
    assert r.total_y == Decimal("100.00")
    # X pierde el automático de A con el recálculo reactivo de siempre.
    assert r.total_x == Decimal("0")
    assert db.query(ConceptoAdicional).filter(
        ConceptoAdicional.linea_id == e.x.id).count() == 0


def test_delete_con_b_reata_antes_del_delete_sin_409(db):
    e = _escenario(db)

    _delete(e, db)

    r = _desde_la_base(db, e)
    assert r.a is None
    assert r.extra.concepto_liquidacion_id == e.b.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA B)"
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")


def test_delete_regla_sin_extras_se_borra_como_hoy(db):
    e = _escenario(db)
    c_id = e.c.id

    respuesta = _delete(e, db, concepto_id=c_id)

    assert respuesta.mensaje == "Concepto eliminado"
    db.expire_all()
    assert db.get(ConceptoLiquidacion, c_id) is None
    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.total_y == Decimal("8100.00")


def test_delete_id_inexistente_404(db):
    e = _escenario(db)

    with pytest.raises(HTTPException) as exc:
        _delete(e, db, concepto_id=9999)

    assert exc.value.status_code == 404


# ─── B5. PATCH /conceptos/precio-masivo ──────────────────────────────────────
# Sin cambio de contrato ni 409: el precio masivo exige precio > 0 (ADR-0016),
# así que nunca deja una regla sin precio y nunca borra extras. La línea X
# (TAREA A) la recalcula el loop de siempre; la Y (TAREA Z), sólo el plan.

def _precio_masivo(db, reglas, precio):
    return precio_masivo(
        datos=ConceptoPrecioMasivoRequest(ids=[r.id for r in reglas], precio=precio),
        db=db,
    )


def test_precio_masivo_solo_a_con_b_reata(db):
    e = _escenario(db)

    respuesta = _precio_masivo(db, [e.a], Decimal("40"))

    assert respuesta.actualizados == 1
    r = _desde_la_base(db, e)
    assert r.a.precio == Decimal("40")
    assert r.a.heredado is False
    assert r.extra.concepto_liquidacion_id == e.b.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA B)"
    assert r.extra.precio == Decimal("1000")
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")
    assert r.total_x == Decimal("320.00")


def test_precio_masivo_a_y_b_sin_otra_opcion_sigue_a_a(db):
    e = _escenario(db)

    respuesta = _precio_masivo(db, [e.a, e.b], Decimal("40"))

    assert respuesta.actualizados == 2
    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA A)"
    assert r.extra.precio == Decimal("40")
    assert r.extra.importe == Decimal("320.00")
    assert r.total_y == Decimal("420.00")
    assert r.total_x == Decimal("320.00")


def test_precio_masivo_a_y_b_a_5000_con_c_fijo_sigue_a_a(db):
    # C ofrece (5000, fijo): coincide en precio pero no en unidad.
    e = _escenario(db)

    _precio_masivo(db, [e.a, e.b], Decimal("5000"))

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.precio == Decimal("5000")
    assert r.extra.unidad_base == "hsjornal"
    assert r.extra.importe == Decimal("40000.00")
    assert r.total_y == Decimal("40100.00")


def test_precio_masivo_a_y_b_a_5000_con_c_hsjornal_sigue_a_a(db):
    # C pasa a ofrecer (5000, hsjornal), lo mismo que A y B después del
    # masivo: la coincidencia nueva no reata el extra a C.
    e = _escenario(db)
    e.c.unidad_base = UnidadBaseConcepto.HSJORNAL
    db.commit()

    _precio_masivo(db, [e.a, e.b], Decimal("5000"))

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA A)"
    assert r.extra.importe == Decimal("40000.00")
    assert r.total_y == Decimal("40100.00")


def test_precio_masivo_de_otra_regla_no_toca_el_extra(db):
    e = _escenario(db)

    _precio_masivo(db, [e.c], Decimal("40"))

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")


def test_precio_masivo_que_borraria_un_extra_frena_sin_escribir(db):
    # Extra viejo de producción (el alta anterior a ADR-0015 no filtraba la
    # categoría): atado a una regla con categoría y sin otra que ofrezca su
    # opción. El masivo no borra trabajo sin confirmación: 409 y no escribe.
    e = _escenario(db, con_b=False)
    e.a.categoria = 3
    db.commit()

    with pytest.raises(HTTPException) as exc:
        _precio_masivo(db, [e.a], Decimal("40"))

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "tipo": "extras_a_revisar",
        "mensaje": "No se aplicó ningún precio: 1 concepto(s) extra en 1 línea(s) "
                   "de Revisión están atados a reglas que ya no se ofrecen como "
                   "extra. Revisalos antes de cambiar el precio.",
        "extras": 1,
        "lineas": 1,
    }
    r = _desde_la_base(db, e)
    assert r.a.precio == Decimal("1000")
    assert r.extra is not None
    assert r.extra.precio == Decimal("1000")
    assert r.extra.importe == Decimal("8000.00")
    assert r.total_y == Decimal("8100.00")

# ─── B6. Documentales ────────────────────────────────────────────────────────
# Lo que el algoritmo NO hace (plan §4 y §8). Sin código nuevo: si alguno
# falla, es un bug de orden.

def _extras_con_codigo(db):
    return db.query(ConceptoAdicional).filter(
        ConceptoAdicional.ingresado_por.isnot(None),
        ConceptoAdicional.codigo_concepto.isnot(None),
    ).all()


def test_regla_nueva_con_la_opcion_no_mueve_el_extra(db):
    # "TAREA 0" va antes que "TAREA A": si la regla nueva reatara, se notaría.
    e = _escenario(db)

    crear_concepto(datos=ConceptoUnifRequest(
        quincena=Q1, tarea_nombre="TAREA 0", codigo=CODIGO,
        unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("1000"),
        tipo=TipoConcepto.REMUNERATIVO,
    ), db=db)

    r = _desde_la_base(db, e)
    assert r.extra.concepto_liquidacion_id == e.a.id
    assert r.extra.descripcion == "Concepto 902 (extra, de TAREA A)"
    assert r.total_y == Decimal("8100.00")


def test_tras_borrar_vuelve_el_precio_y_el_extra_no(db):
    e = _escenario(db, con_b=False)
    _delete(e, db, confirmar_borrado_extras=True)

    crear_concepto(datos=ConceptoUnifRequest(
        quincena=Q1, tarea_nombre="TAREA A", codigo=CODIGO,
        unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("1000"),
        tipo=TipoConcepto.REMUNERATIVO,
    ), db=db)

    r = _desde_la_base(db, e)
    assert r.extra is None
    assert _extras_con_codigo(db) == []
    assert r.total_y == Decimal("100.00")
    assert r.total_x == Decimal("8000.00")


@pytest.mark.parametrize("con_b,accion", [
    (True, lambda e, db: _patch(e, db, precio=Decimal("1200"))),
    (False, lambda e, db: _patch(e, db, precio=Decimal("1200"))),
    (True, lambda e, db: _patch(e, db, categoria=3)),
    (False, lambda e, db: _patch(e, db, categoria=3, confirmar_borrado_extras=True)),
    (True, lambda e, db: _delete(e, db)),
    (False, lambda e, db: _delete(e, db, confirmar_borrado_extras=True)),
    (True, lambda e, db: _precio_masivo(db, [e.a], Decimal("40"))),
    (True, lambda e, db: _precio_masivo(db, [e.a, e.b], Decimal("40"))),
], ids=[
    "patch_reata", "patch_sigue", "patch_categoria_reata", "patch_categoria_borra",
    "delete_reata", "delete_borra", "masivo_reata", "masivo_sigue",
])
def test_manual_libre_intacto(db, con_b, accion):
    e = _escenario(db, con_b=con_b)

    accion(e, db)

    db.expire_all()
    manual = db.query(ConceptoAdicional).filter(ConceptoAdicional.id == e.manual.id).first()
    assert manual is not None
    assert manual.descripcion == "Plus a mano"
    assert manual.importe == Decimal("100.00")
    assert manual.tipo == TipoConcepto.OTRO
    assert manual.concepto_liquidacion_id is None
    assert manual.codigo_concepto is None
    assert manual.linea_id == e.y.id
