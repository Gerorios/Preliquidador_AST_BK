"""Verificaciones por fuente (etapa 9): lo que hay que mirar antes de liquidar.

Lo que cuidan estos tests es que no se avise de más ni de menos. Una pantalla
que lista lo que no importa se deja de leer, y una que se calla un duplicado
deja que se cobre dos veces.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CargaCombustible, HoraReparacion, Liquidacion, Viaje,
)
from app.modulos.terceros.services.verificaciones_service import (
    VerificacionesService,
)

Q = date(2026, 8, 1)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add(Liquidacion(quincena=Q))
    sesion.commit()
    yield sesion
    sesion.close()


@pytest.fixture()
def verificaciones(db):
    return VerificacionesService(db)


def _liq(db) -> Liquidacion:
    return db.query(Liquidacion).filter(Liquidacion.quincena == Q).first()


def carga(db, **campos):
    base = dict(tercero="ARANDA, HUGO", fecha_uso=Q, colectivo_patente="FAP480",
                vale="60023", litros=Decimal("150"), origen="SHELL")
    db.add(CargaCombustible(liquidacion_id=_liq(db).id, **{**base, **campos}))
    db.commit()


def viaje(db, **campos):
    base = dict(tercero="ARANDA, HUGO", fecha_uso=Q, colectivo_patente="FAP480",
                cliente="SAN MIGUEL", finca="CASPINCHANGO", capataz="SOSA",
                chofer="ACOSTA", tarea="COSECHA",
                cantidad_viajes=Decimal("1"), cant_personas=30)
    db.add(Viaje(liquidacion_id=_liq(db).id, **{**base, **campos}))
    db.commit()


def de(salida, fuente):
    return next(f for f in salida if f["fuente"] == fuente)


def tipos(salida, fuente):
    return [v["tipo"] for v in de(salida, fuente)["verificaciones"]]


# ─── Duplicados ─────────────────────────────────────────────────────────────

def test_dos_filas_con_la_misma_clave_son_un_duplicado(db, verificaciones):
    """La clave es la misma que usa la reconciliación: si dos filas la
    comparten, el origen no tiene forma de distinguirlas."""
    db.add_all([
        HoraReparacion(liquidacion_id=_liq(db).id, tercero="PABLO ROJAS",
                       fecha=Q, id_maquina=735, sub_rubro="475. TORRE",
                       estado="Pendiente", horas_total=Decimal("5")),
        HoraReparacion(liquidacion_id=_liq(db).id, tercero="PABLO ROJAS",
                       fecha=Q, id_maquina=735, sub_rubro="475. TORRE",
                       estado="Pendiente", horas_total=Decimal("5")),
    ])
    db.commit()

    v = de(verificaciones.por_fuente(Q), "horas_reparacion")["verificaciones"][0]
    assert v["tipo"] == "duplicado"
    assert v["severidad"] == "alta"
    assert v["total"] == 1
    assert v["casos"][0]["veces"] == 2
    assert v["sistema"] == "App del taller"


def test_dos_filas_que_se_diferencian_en_algo_no_son_duplicado(db, verificaciones):
    db.add_all([
        HoraReparacion(liquidacion_id=_liq(db).id, tercero="PABLO ROJAS",
                       fecha=Q, id_maquina=735, sub_rubro="475. TORRE",
                       estado="Pendiente", horas_total=Decimal("5")),
        HoraReparacion(liquidacion_id=_liq(db).id, tercero="PABLO ROJAS",
                       fecha=Q, id_maquina=735, sub_rubro="475. TORRE",
                       estado="Pendiente", horas_total=Decimal("3")),
    ])
    db.commit()

    assert tipos(verificaciones.por_fuente(Q), "horas_reparacion") == []


# ─── Lo propio del combustible ──────────────────────────────────────────────

def test_el_mismo_vale_en_dos_cargas_distintas_se_avisa(db, verificaciones):
    """Un vale es una carga. Repetido, una de las dos sobra."""
    carga(db, vale="60300", litros=Decimal("150"))
    carga(db, vale="60300", litros=Decimal("1"))

    v = next(x for x in de(verificaciones.por_fuente(Q), "combustible")["verificaciones"]
             if x["tipo"] == "vale_repetido")
    assert v["severidad"] == "alta"
    assert v["total"] == 1


def test_un_vale_repetido_que_ya_salio_como_duplicado_no_se_cuenta_dos_veces(db, verificaciones):
    """Es el mismo problema dicho de dos formas, y una pantalla que cuenta dos
    veces lo mismo deja de ser confiable."""
    carga(db, vale="60245")
    carga(db, vale="60245")      # idéntica: ya es duplicado exacto

    salida = tipos(verificaciones.por_fuente(Q), "combustible")
    assert salida == ["duplicado"]


def test_una_carga_sin_vale_no_se_va_a_poder_conciliar(db, verificaciones):
    carga(db, vale=None)

    v = next(x for x in de(verificaciones.por_fuente(Q), "combustible")["verificaciones"]
             if x["tipo"] == "carga_sin_vale")
    assert v["severidad"] == "media"
    assert v["total"] == 1


# ─── Lo propio de los viajes ────────────────────────────────────────────────

def test_un_viaje_en_cero_se_avisa_pero_no_como_urgente(db, verificaciones):
    """Cero viajes son cero pesos y puede ser legítimo. Se avisa para que
    alguien decida, no para corregir a ciegas."""
    viaje(db, cantidad_viajes=Decimal("0"))
    viaje(db, capataz="OTRO")

    v = de(verificaciones.por_fuente(Q), "viajes")["verificaciones"][0]
    assert v["tipo"] == "viaje_en_cero"
    assert v["severidad"] == "baja"
    assert v["total"] == 1


# ─── La forma de la salida ──────────────────────────────────────────────────

def test_una_fuente_limpia_viene_igual_con_la_lista_vacia(db, verificaciones):
    """Si desapareciera, nadie sabría si está bien o si no se miró."""
    salida = verificaciones.por_fuente(Q)
    assert [f["fuente"] for f in salida] == [
        "viajes", "horas_servicio", "combustible", "repuestos", "horas_reparacion"]
    assert all(f["verificaciones"] == [] for f in salida)


def test_cada_fuente_dice_donde_se_corrige(db, verificaciones):
    """Es lo que el liquidador necesita: a quién avisarle."""
    salida = {f["fuente"]: f["sistema"] for f in verificaciones.por_fuente(Q)}
    assert salida["viajes"] == "Sistema de campo"
    assert salida["repuestos"] == "Sistema de compras"
    assert salida["horas_reparacion"] == "App del taller"


def test_una_quincena_sin_generar_no_rompe(verificaciones):
    assert verificaciones.por_fuente(date(2026, 12, 1)) == []
