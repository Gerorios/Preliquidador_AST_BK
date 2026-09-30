"""En qué quincena se liquida cada hecho: moverlo entero, o repartir un
repuesto en cuotas.

Lo que estos tests cuidan es que **nada se descuente dos veces ni se pierda**:
un repuesto en cuotas no puede descontarse además entero en su quincena, y la
suma de las cuotas tiene que dar el importe exacto al centavo.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CALCULADO, NO_COBRAR, CuotaRepuesto, Liquidacion, Repuesto, Viaje,
)
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.destino_service import (
    DestinoInvalido, DestinoService, repartir,
)
from app.modulos.terceros.services.grilla_service import GrillaService
from app.modulos.terceros.services.tarifario_service import TarifarioService

Q = date(2026, 8, 1)
S = date(2026, 8, 16)
SEPT = date(2026, 9, 1)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add_all([Liquidacion(quincena=Q), Liquidacion(quincena=S)])
    sesion.commit()
    yield sesion
    sesion.close()


@pytest.fixture()
def destino(db):
    return DestinoService(db)


def _liq(db, q=Q) -> Liquidacion:
    return db.query(Liquidacion).filter(Liquidacion.quincena == q).first()


def viaje(db, q=Q, **campos) -> Viaje:
    base = dict(tercero="ARANDA, HUGO", cliente="SAN MIGUEL",
                finca="CASPINCHANGO", capataz="SOSA", cantidad_viajes=1)
    fila = Viaje(liquidacion_id=_liq(db, q).id, **{**base, **campos})
    db.add(fila)
    db.commit()
    return fila


def repuesto(db, monto="100000", q=Q, **campos) -> Repuesto:
    base = dict(tercero="ARANDA, HUGO", maquina="COLECTIVO FAP480",
                repuesto="EMBRAGUE", fecha=q, monto_total=Decimal(monto))
    fila = Repuesto(liquidacion_id=_liq(db, q).id, **{**base, **campos})
    db.add(fila)
    db.commit()
    CalculoService(db).calcular(q, ("repuestos",))
    db.refresh(fila)
    return fila


def repuestos_de(db, quincena) -> Decimal:
    """Cuánto se le descuenta a ARANDA en repuestos en esa quincena."""
    filas = CalculoService(db).totales(quincena)
    return next((f["repuestos"] for f in filas if f["tercero"] == "ARANDA, HUGO"),
                Decimal("0"))


# ─── Repartir un importe ────────────────────────────────────────────────────

def test_las_cuotas_suman_exacto_y_la_ultima_absorbe_el_redondeo():
    cuotas = repartir(Decimal("100000.00"), 3)
    assert cuotas == [Decimal("33333.33"), Decimal("33333.33"), Decimal("33333.34")]
    assert sum(cuotas) == Decimal("100000.00")


def test_la_ultima_cuota_nunca_es_mas_chica_que_las_demas():
    """Se leería como un error. Por eso se redondea hacia abajo."""
    cuotas = repartir(Decimal("100.00"), 6)
    assert all(c <= cuotas[-1] for c in cuotas)
    assert sum(cuotas) == Decimal("100.00")


def test_si_divide_justo_son_todas_iguales():
    assert repartir(Decimal("1000.00"), 4) == [Decimal("250.00")] * 4


# ─── Mover un hecho entero ──────────────────────────────────────────────────

def test_un_hecho_movido_se_liquida_en_la_otra_quincena(db, destino):
    v = viaje(db)
    destino.mover("viajes", v.id, S, "llegó tarde")

    grilla_q = GrillaService(db).lineas(Q)
    grilla_s = GrillaService(db).lineas(S)
    assert [f["id"] for f in grilla_q if f["concepto"] == "viajes"] == []
    movido = next(f for f in grilla_s if f["concepto"] == "viajes")
    assert movido["viene_de"] == Q
    assert movido["motivo"] == "llegó tarde"


def test_mover_de_quincena_pide_el_motivo(db, destino):
    """El recibo lo muestra como un ajuste: sin motivo no se puede leer."""
    v = viaje(db)
    with pytest.raises(DestinoInvalido):
        destino.mover("viajes", v.id, S, "   ")


def test_volver_a_su_quincena_deshace_el_movimiento_sin_pedir_motivo(db, destino):
    v = viaje(db)
    destino.mover("viajes", v.id, S, "llegó tarde")
    destino.mover("viajes", v.id, Q, None)

    db.refresh(v)
    assert v.quincena_efectiva is None and v.motivo_efectiva is None


def test_una_quincena_empieza_el_1_o_el_16(db, destino):
    v = viaje(db)
    with pytest.raises(DestinoInvalido):
        destino.mover("viajes", v.id, date(2026, 8, 10), "x")


def test_moverlo_de_quincena_no_le_cambia_el_precio(db, destino):
    """Cambia cuándo se cobra, no cuánto: un viaje que llegó tarde se paga lo
    que valía en la quincena en que se generó."""
    tarifario = TarifarioService(db)
    tarifario.crear("viajes", Q, {"precio": "100000"})
    tarifario.crear("viajes", S, {"precio": "120000"})
    v = viaje(db)
    CalculoService(db).calcular(Q)

    destino.mover("viajes", v.id, S, "llegó tarde")
    CalculoService(db).calcular(S)
    CalculoService(db).calcular(Q)
    db.refresh(v)
    assert v.importe == Decimal("100000.00")


def test_la_tarifa_de_la_quincena_a_la_que_va_no_lo_alcanza(db, destino):
    tarifario = TarifarioService(db)
    tarifario.crear("viajes", Q, {"precio": "100000"})
    v = viaje(db)
    destino.mover("viajes", v.id, S, "llegó tarde")

    tarifario.crear("viajes", S, {"tercero": "ARANDA, HUGO", "precio": "150000"})
    CalculoService(db).calcular(S)
    CalculoService(db).calcular(Q)

    db.refresh(v)
    assert v.importe == Decimal("100000.00")


def test_si_le_falta_la_tarifa_le_falta_en_su_quincena(db, destino):
    """El Tarifario pide el precio donde se cobra: en la quincena en que se
    generó, no en la que se liquida. Si no, se pactaría en la quincena
    equivocada y el viaje seguiría sin precio."""
    v = viaje(db)
    CalculoService(db).calcular(Q)
    destino.mover("viajes", v.id, S, "llegó tarde")

    calculo = CalculoService(db)
    en_q = calculo.combinaciones("viajes", Q)
    en_s = calculo.combinaciones("viajes", S)
    assert sum(c["sin_precio"] for c in en_q) == 1
    assert en_s == []


# ─── Repartir un repuesto en cuotas ─────────────────────────────────────────

def test_un_repuesto_en_cuotas_se_descuenta_en_partes_y_no_entero(db, destino):
    r = repuesto(db, "90000")
    assert repuestos_de(db, Q) == Decimal("90000.00")

    destino.repartir_en_cuotas(r.id, Q, 3)
    assert repuestos_de(db, Q) == Decimal("30000.00")
    assert repuestos_de(db, S) == Decimal("30000.00")
    assert repuestos_de(db, SEPT) == Decimal("30000.00")


def test_las_cuotas_pueden_empezar_despues_de_su_quincena(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, S, 2)

    assert repuestos_de(db, Q) == Decimal("0")
    assert repuestos_de(db, S) == Decimal("45000.00")
    assert repuestos_de(db, SEPT) == Decimal("45000.00")


def test_la_cuota_aparece_en_la_grilla_con_su_numero(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3, "se le financia")

    en_q = [f for f in GrillaService(db).lineas(Q) if f["concepto"] == "repuestos"]
    en_s = [f for f in GrillaService(db).lineas(S) if f["concepto"] == "repuestos"]
    assert [(f["cuota"], f["importe"], f["viene_de"]) for f in en_q] == [
        ("1 de 3", Decimal("30000.00"), None)]
    assert [(f["cuota"], f["viene_de"], f["motivo"]) for f in en_s] == [
        ("2 de 3", Q, "se le financia")]


def test_la_portada_suma_las_cuotas_en_su_quincena(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3)

    por_quincena = CalculoService(db).importes_por_quincena()
    assert por_quincena[Q]["repuestos"] == Decimal("30000.00")
    assert por_quincena[SEPT]["repuestos"] == Decimal("30000.00")


def test_repartir_de_nuevo_reemplaza_el_plan_y_no_suma(db, destino):
    """Dos planes a la vez le descontarían el mismo repuesto dos veces."""
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3)
    destino.repartir_en_cuotas(r.id, Q, 2)

    assert db.query(CuotaRepuesto).count() == 2
    assert repuestos_de(db, Q) == Decimal("45000.00")


def test_repartir_pisa_un_movimiento_anterior(db, destino):
    r = repuesto(db, "90000")
    destino.mover("repuestos", r.id, S, "se posterga")
    destino.repartir_en_cuotas(r.id, Q, 2)

    db.refresh(r)
    assert r.quincena_efectiva is None
    assert repuestos_de(db, Q) == Decimal("45000.00")


def test_un_repuesto_en_cuotas_no_se_puede_ademas_mover(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3)
    with pytest.raises(DestinoInvalido):
        destino.mover("repuestos", r.id, S, "x")


def test_quitar_las_cuotas_lo_vuelve_a_descontar_entero(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3)
    destino.quitar_cuotas(r.id)

    assert repuestos_de(db, Q) == Decimal("90000.00")
    assert repuestos_de(db, S) == Decimal("0")


@pytest.mark.parametrize("cuotas", [1, 0, 25])
def test_las_cuotas_van_de_2_a_24(db, destino, cuotas):
    r = repuesto(db, "90000")
    with pytest.raises(DestinoInvalido):
        destino.repartir_en_cuotas(r.id, Q, cuotas)


def test_un_repuesto_que_no_se_cobra_no_se_reparte(db, destino):
    """Sin importe una cuota de cero pasaría por un descuento hecho."""
    r = repuesto(db, "90000", no_cobrar=True)
    assert r.estado_calculo == NO_COBRAR
    with pytest.raises(DestinoInvalido):
        destino.repartir_en_cuotas(r.id, Q, 3)


def test_si_deja_de_cobrarse_sus_cuotas_tampoco_se_suman(db, destino):
    r = repuesto(db, "90000")
    destino.repartir_en_cuotas(r.id, Q, 3)

    r.no_cobrar = True
    db.commit()
    CalculoService(db).calcular(Q, ("repuestos",))

    assert repuestos_de(db, S) == Decimal("0")
