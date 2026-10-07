"""Tests de caracterización de PreliquidacionService.listar_lineas,
actualizar_linea y legajos_disponibles_de_linea (PR3, paso 3.1).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
datos de personas son ficticios.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.sueldos_service import SueldosService
from app.modulos.preliquidacion.models import (
    AjusteManual, ConceptoAdicional, Preliquidacion, PreliquidacionLinea,
)
from app.modulos.preliquidacion.schemas import LineaUpdateRequest
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _sueldos_con(por_cuil: dict) -> SueldosService:
    """SueldosService con el cache ya poblado a mano (sin BD externa real)."""
    s = SueldosService.__new__(SueldosService)
    s._cache_cargado = True
    s._por_legajo = {}
    s._por_legajo_empresa = {}
    s._por_cuil = por_cuil
    return s


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, nombre_empleado="PERSONA UNO", cuit="20000000001",
           empresa_asignada="LA ASTURIANA", fecha_tarea=date(2026, 5, 2), **extra):
    datos = dict(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit=cuit, nombre_empleado=nombre_empleado, legajo_campo="0001",
        empresa_asignada=empresa_asignada, legajo_asignado="0001",
        fecha_tarea=fecha_tarea,
        # Línea "limpia" por defecto: el modelo trae linea_incompleta=True
        # como default, así que hay que apagarlo explícitamente.
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


def _concepto(db, linea, importe):
    c = ConceptoAdicional(linea_id=linea.id, descripcion="Concepto de prueba", importe=Decimal(importe))
    db.add(c)
    db.commit()
    return c


# ─── listar_lineas ────────────────────────────────────────────────────────────

def test_listar_sin_filtros_ordena_por_empresa_empleado_fecha_y_trae_conceptos(db):
    preliq = _preliq(db)
    otra = _preliq(db, quincena=date(2026, 5, 16))
    c = _linea(db, preliq, "PERSONA DOS", empresa_asignada="PAMPLONA", fecha_tarea=date(2026, 5, 3))
    b = _linea(db, preliq, "PERSONA UNO", empresa_asignada="LA ASTURIANA", fecha_tarea=date(2026, 5, 5))
    a = _linea(db, preliq, "PERSONA UNO", empresa_asignada="LA ASTURIANA", fecha_tarea=date(2026, 5, 4))
    d = _linea(db, preliq, "PERSONA CERO", empresa_asignada="PAMPLONA", fecha_tarea=date(2026, 5, 9))
    _linea(db, otra, "PERSONA DE OTRA QUINCENA")
    _concepto(db, a, "100")
    _concepto(db, a, "50")

    lineas = PreliquidacionService(db).listar_lineas(preliq.id)

    assert [l.id for l in lineas] == [a.id, b.id, d.id, c.id]
    # conceptos cargados (selectinload): accesibles sin query extra
    assert "conceptos" in lineas[0].__dict__
    assert sorted(x.importe for x in lineas[0].conceptos) == [Decimal("50"), Decimal("100")]
    assert lineas[1].__dict__["conceptos"] == []


def test_listar_filtra_empresa_en_mayusculas(db):
    preliq = _preliq(db)
    pamp = _linea(db, preliq, "PERSONA UNO", empresa_asignada="PAMPLONA")
    _linea(db, preliq, "PERSONA DOS", empresa_asignada="LA ASTURIANA")

    lineas = PreliquidacionService(db).listar_lineas(preliq.id, empresa="pamplona")

    assert [l.id for l in lineas] == [pamp.id]


def test_listar_solo_alertas_no_incluye_alerta_empresa(db):
    preliq = _preliq(db)
    dup = _linea(db, preliq, "PERSONA A", es_duplicado=True)
    leg = _linea(db, preliq, "PERSONA B", alerta_legajo=True)
    inc = _linea(db, preliq, "PERSONA C", linea_incompleta=True)
    pos = _linea(db, preliq, "PERSONA F", es_posible_duplicado=True)
    _linea(db, preliq, "PERSONA D", alerta_empresa=True)  # sólo alerta_empresa: NO entra
    _linea(db, preliq, "PERSONA E")  # limpia

    lineas = PreliquidacionService(db).listar_lineas(preliq.id, solo_alertas=True)

    # Revision.jsx replica esta misma condición en cliente (sin alerta_empresa).
    assert {l.id for l in lineas} == {dup.id, leg.id, inc.id, pos.id}


def test_listar_nombre_empleado_es_ilike_case_insensitive(db):
    preliq = _preliq(db)
    p1 = _linea(db, preliq, "PERSONA UNO")
    p2 = _linea(db, preliq, "SUPERVISADO DOS")  # "per" en el medio también matchea
    _linea(db, preliq, "OTRO EMPLEADO")

    lineas = PreliquidacionService(db).listar_lineas(preliq.id, nombre_empleado="per")

    assert {l.id for l in lineas} == {p1.id, p2.id}


def test_listar_preliquidacion_inexistente_devuelve_lista_vacia(db):
    preliq = _preliq(db)
    _linea(db, preliq)

    assert PreliquidacionService(db).listar_lineas(preliq.id + 999) == []


# ─── actualizar_linea ─────────────────────────────────────────────────────────

def test_actualizar_empresa_audita_apaga_alerta_y_recalcula_importe(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, empresa_asignada="LA ASTURIANA", alerta_legajo=True,
                   importe_total=Decimal("999"))
    _concepto(db, linea, "100")
    _concepto(db, linea, "25.50")

    svc = PreliquidacionService(db)
    res = svc.actualizar_linea(
        linea.id,
        LineaUpdateRequest(empresa_asignada="PAMPLONA", motivo_ajuste="cambio de empresa"),
        usuario_id=7,
    )

    assert res.id == linea.id
    db.refresh(linea)
    assert linea.empresa_asignada == "PAMPLONA"
    assert linea.alerta_legajo is False
    # importe_total = suma de conceptos (pisa el 999 previo); importe_base = 0
    assert linea.importe_total == Decimal("125.50")
    assert linea.importe_base == Decimal("0")

    ajustes = db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).all()
    assert len(ajustes) == 1
    a = ajustes[0]
    assert a.campo_modificado == "empresa_asignada"
    assert a.valor_anterior == "LA ASTURIANA"
    assert a.valor_nuevo == "PAMPLONA"
    assert a.motivo == "cambio de empresa"
    assert a.usuario_id == 7


def test_actualizar_con_mismo_valor_no_graba_ajuste(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, empresa_asignada="LA ASTURIANA", legajo_asignado="0001", alerta_legajo=True)

    PreliquidacionService(db).actualizar_linea(
        linea.id,
        LineaUpdateRequest(empresa_asignada="LA ASTURIANA", legajo_asignado="0001"),
        usuario_id=7,
    )

    assert db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).count() == 0
    db.refresh(linea)
    assert linea.empresa_asignada == "LA ASTURIANA"
    # Comportamiento actual: alerta_legajo se apaga siempre que venga
    # empresa_asignada en el request, aunque sea el mismo valor.
    assert linea.alerta_legajo is False


def test_actualizar_campo_none_no_se_toca(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, empresa_asignada="LA ASTURIANA", legajo_asignado="0001",
                   grupo_pago_aplicado="PLANTA", observacion="nota previa", alerta_legajo=True)

    PreliquidacionService(db).actualizar_linea(
        linea.id, LineaUpdateRequest(legajo_asignado="0002"), usuario_id=7,
    )

    db.refresh(linea)
    assert linea.legajo_asignado == "0002"
    assert linea.empresa_asignada == "LA ASTURIANA"
    assert linea.grupo_pago_aplicado == "PLANTA"
    assert linea.observacion == "nota previa"
    # sin empresa_asignada en el request, la alerta queda como estaba
    assert linea.alerta_legajo is True
    ajustes = db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).all()
    assert [a.campo_modificado for a in ajustes] == ["legajo_asignado"]


def test_actualizar_observacion_tambien_audita(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, observacion=None)

    PreliquidacionService(db).actualizar_linea(
        linea.id, LineaUpdateRequest(observacion="revisar horas", motivo_ajuste="nota"), usuario_id=3,
    )

    db.refresh(linea)
    assert linea.observacion == "revisar horas"
    ajustes = db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).all()
    assert len(ajustes) == 1
    assert ajustes[0].campo_modificado == "observacion"
    # Comportamiento actual: el anterior se guarda con str(), así que un
    # NULL queda auditado como el texto "None".
    assert ajustes[0].valor_anterior == "None"
    assert ajustes[0].valor_nuevo == "revisar horas"
    assert ajustes[0].motivo == "nota"
    assert ajustes[0].usuario_id == 3


def test_actualizar_linea_inexistente_levanta_value_error(db):
    with pytest.raises(ValueError, match=r"^Línea 12345 no encontrada$"):
        PreliquidacionService(db).actualizar_linea(12345, LineaUpdateRequest(), usuario_id=1)


# ─── legajos_disponibles_de_linea ─────────────────────────────────────────────

def test_legajos_disponibles_con_cuil_y_maestro(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, cuit=" 20000000001 ", empresa_asignada="LA ASTURIANA", legajo_asignado="0001")
    svc = PreliquidacionService(db)
    svc.sueldos = _sueldos_con({
        "20000000001": [
            {"empresa": "LA ASTURIANA", "legajo": "0001", "apellido_nombre": "PERSONA UNO"},
            {"empresa": "PAMPLONA", "legajo": "0901", "apellido_nombre": "PERSONA UNO"},
        ],
    })

    res = svc.legajos_disponibles_de_linea(linea.id)

    assert res == {
        "cuil": "20000000001",
        "empresa_asignada": "LA ASTURIANA",
        "legajo_asignado": "0001",
        "legajos_disponibles": [
            {"empresa": "LA ASTURIANA", "legajo": "0001"},
            {"empresa": "PAMPLONA", "legajo": "0901"},
        ],
    }


@pytest.mark.parametrize("cuit", [None, "", "   "])
def test_legajos_disponibles_sin_cuil(db, cuit):
    preliq = _preliq(db)
    linea = _linea(db, preliq, cuit=cuit)
    svc = PreliquidacionService(db)
    svc.sueldos = _sueldos_con({"20000000001": [{"empresa": "LA ASTURIANA", "legajo": "0001"}]})

    res = svc.legajos_disponibles_de_linea(linea.id)

    assert res["cuil"] is None
    assert res["legajos_disponibles"] == []


def test_legajos_disponibles_sin_servicio_de_sueldos(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, cuit="20000000001")
    svc = PreliquidacionService(db)  # sin db_sueldos
    assert svc.sueldos is None

    res = svc.legajos_disponibles_de_linea(linea.id)

    assert res["cuil"] == "20000000001"
    assert res["legajos_disponibles"] == []


def test_legajos_disponibles_linea_inexistente_levanta_value_error(db):
    with pytest.raises(ValueError, match=r"^Línea 777 no encontrada$"):
        PreliquidacionService(db).legajos_disponibles_de_linea(777)
