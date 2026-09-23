"""La grilla de la quincena (etapa 8): los seis conceptos en una sola lista.

Lo que se cuida acá es que cada dato salga **en su campo** y no pegado en un
texto. Una columna que diga "HIH521 · MEDINA, HECTOR · CORTO" se ve bien y no se
puede ordenar por patente, ni filtrar por chofer, ni exportar a una planilla que
sirva para algo.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CALCULADO, NO_APROBADA, SIN_TARIFA, UNIDAD_HORA_MAQUINA,
    CargaCombustible, HoraReparacion, HoraServicio, Liquidacion, PrecioSeguro,
    Repuesto, Viaje,
)
from app.modulos.terceros.services.grilla_service import GrillaService

Q = date(2026, 8, 1)
SIGUIENTE = date(2026, 8, 16)


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
def grilla(db):
    return GrillaService(db)


def _liq(db, quincena=Q) -> Liquidacion:
    return db.query(Liquidacion).filter(Liquidacion.quincena == quincena).first()


def _una(filas, concepto):
    return next(f for f in filas if f["concepto"] == concepto)


# ─── Cada dato en su campo ──────────────────────────────────────────────────

def test_un_viaje_trae_patente_chofer_y_tipo_por_separado(db, grilla):
    db.add(Viaje(
        liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO", fecha_uso=Q,
        colectivo_patente=" HIH521", chofer="MEDINA, HECTOR MARTIN",
        cliente="SAN MIGUEL", finca="CASPINCHANGO", capataz="LEDESMA",
        tarea="COSECHA", cantidad_viajes=Decimal("1"), tipo_viaje="CORTO",
        precio_aplicado=Decimal("205000"), importe=Decimal("205000"),
        estado_calculo=CALCULADO))
    db.commit()

    f = _una(grilla.lineas(Q), "viajes")
    assert f["patente"] == "HIH521"        # y sin el espacio del origen
    assert f["chofer"] == "MEDINA, HECTOR MARTIN"
    assert f["tipo_viaje"] == "CORTO"
    assert f["capataz"] == "LEDESMA"
    assert f["importe"] == Decimal("205000")
    assert f["signo"] == 1                  # se le paga


def test_una_carga_trae_estacion_y_vale_por_separado(db, grilla):
    db.add(CargaCombustible(
        liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO", fecha_uso=Q,
        colectivo_patente="FAP480", vale="60023", origen="SHELL FAMAILLA",
        litros=Decimal("150"), precio_aplicado=Decimal("2035.24"),
        importe=Decimal("305286"), estado_calculo=CALCULADO))
    db.commit()

    f = _una(grilla.lineas(Q), "combustible")
    assert f["estacion"] == "SHELL FAMAILLA"
    assert f["vale"] == "60023"
    assert f["patente"] == "FAP480"
    assert f["signo"] == -1                 # se le descuenta
    # Un combustible no tiene capataz ni finca: no se rellenan.
    assert f["capataz"] is None and f["finca"] is None


def test_una_hora_de_taller_trae_el_sub_rubro_en_su_campo(db, grilla):
    db.add(HoraReparacion(
        liquidacion_id=_liq(db).id, tercero="PABLO ROJAS", fecha=Q,
        maquina="CARGADORA MANITOU N°9872", rubro="HIDRAULICA",
        sub_rubro="475. TORRE", finca="EL CORTE", estado="Pendiente",
        horas_total=Decimal("5"), importe=Decimal("0"),
        estado_calculo=NO_APROBADA))
    db.commit()

    f = _una(grilla.lineas(Q), "reparacion")
    assert f["sub_rubro"] == "475. TORRE"
    assert f["rubro"] == "HIDRAULICA"
    assert f["maquina"] == "CARGADORA MANITOU N°9872"
    # El estado del taller y el del cálculo son dos cosas distintas, y la
    # pantalla muestra las dos: una explica a la otra.
    assert f["estado_taller"] == "Pendiente"
    assert f["estado"] == NO_APROBADA


def test_un_repuesto_trae_maquina_repuesto_y_rubro(db, grilla):
    db.add(Repuesto(
        liquidacion_id=_liq(db).id, tercero="RUBEN MUÑOZ", fecha=Q,
        maquina="SER-TEC", repuesto='TORNILLO 3/8X2"', rubro="BULONERIA",
        cantidad=Decimal("3"), monto_total=Decimal("789.81"),
        importe=Decimal("789.81"), estado_calculo=CALCULADO))
    db.commit()

    f = _una(grilla.lineas(Q), "repuestos")
    assert (f["maquina"], f["repuesto"], f["rubro"]) == (
        "SER-TEC", 'TORNILLO 3/8X2"', "BULONERIA")
    # No lleva precio unitario: el que tiene es del sistema de compras, no uno
    # pactado con el tercero.
    assert f["precio"] is None


def test_una_hora_de_servicio_dice_sobre_que_medida_se_paga(db, grilla):
    db.add(HoraServicio(
        liquidacion_id=_liq(db).id, tercero="BARRIOS", fecha=Q,
        planilla="MAQUINARIA", cliente="CITROMAX", finca="TAJAMAR 2",
        tarea="CARGA FRUTA POR BINS", maquinaria="MANITOU N°0060",
        horas_maquina=Decimal("6"), unidades=Decimal("297"),
        unidad_base=UNIDAD_HORA_MAQUINA, cantidad_base=Decimal("6"),
        precio_aplicado=Decimal("10000"), importe=Decimal("60000"),
        estado_calculo=CALCULADO))
    db.commit()

    f = _una(grilla.lineas(Q), "servicio")
    assert f["maquina"] == "MANITOU N°0060"
    assert f["planilla"] == "MAQUINARIA"
    # La fila tiene las dos medidas cargadas; la que se cobró es ésta.
    assert f["unidad"] == UNIDAD_HORA_MAQUINA
    assert f["cantidad"] == Decimal("6")


def test_un_seguro_es_la_tarifa_y_no_tiene_fecha(db, grilla):
    """Los seguros no tienen tabla de hechos: se imputan a la quincena entera."""
    db.add(PrecioSeguro(
        quincena=Q, tercero="CORNEJO, MATIAS", tipo_seguro="AUTOMOTOR",
        sujeto="MERCEDES 1114", referencia="ABC123", importe=Decimal("30000")))
    db.commit()

    f = _una(grilla.lineas(Q), "seguros")
    assert f["fecha"] is None
    assert (f["sujeto"], f["referencia"], f["tipo_seguro"]) == (
        "MERCEDES 1114", "ABC123", "AUTOMOTOR")
    assert f["signo"] == -1
    assert f["importe"] == Decimal("30000")


# ─── Qué entra y qué no ─────────────────────────────────────────────────────

def test_las_lineas_sin_precio_tambien_vienen(db, grilla):
    """Son las que hay que resolver: esconderlas sería esconder el trabajo."""
    db.add(Viaje(liquidacion_id=_liq(db).id, tercero="SIN PACTAR", fecha_uso=Q,
                 cantidad_viajes=Decimal("1"), importe=Decimal("0"),
                 estado_calculo=SIN_TARIFA))
    db.commit()

    f = _una(grilla.lineas(Q), "viajes")
    assert f["estado"] == SIN_TARIFA
    assert f["precio"] is None


def test_un_hecho_diferido_aparece_en_la_quincena_en_que_se_cobra(db, grilla):
    db.add(Liquidacion(quincena=SIGUIENTE))
    db.commit()
    db.add(Viaje(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                 fecha_uso=Q, cantidad_viajes=Decimal("1"),
                 quincena_efectiva=SIGUIENTE, motivo_efectiva="llegó tarde",
                 importe=Decimal("200000"), estado_calculo=CALCULADO))
    db.commit()

    assert grilla.lineas(Q) == []
    assert len(grilla.lineas(SIGUIENTE)) == 1


def test_los_seguros_van_al_final_porque_no_tienen_fecha(db, grilla):
    db.add(Viaje(liquidacion_id=_liq(db).id, tercero="ARANDA", fecha_uso=Q,
                 cantidad_viajes=Decimal("1"), importe=Decimal("1"),
                 estado_calculo=CALCULADO))
    db.add(PrecioSeguro(quincena=Q, tercero="ARANDA", tipo_seguro="AUTOMOTOR",
                        sujeto="X", importe=Decimal("1")))
    db.commit()

    assert [f["concepto"] for f in grilla.lineas(Q)] == ["viajes", "seguros"]


def test_una_quincena_sin_generar_no_rompe(grilla):
    assert grilla.lineas(date(2026, 12, 1)) == []
