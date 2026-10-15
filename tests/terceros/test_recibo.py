"""El recibo (etapa 11): los bloques, la emisión que lo congela, la factura,
el pago y la cuenta corriente.

Lo que estos tests cuidan es que **lo que se le manda a un tercero no cambie
solo** y que **el saldo cierre**: lo que se le debía, menos lo que se le pagó,
es lo que arranca la quincena siguiente.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    FACTURA_APROBADA, FACTURA_RECHAZADA, FACTURA_RECIBIDA, PAGO_PARCIAL,
    PAGO_TOTAL, Liquidacion, PrecioSeguro, ReciboEvento, Repuesto, Viaje,
)
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.destino_service import (
    DestinoInvalido, DestinoService,
)
from app.modulos.terceros.services.recibo_service import (
    ReciboInvalido, ReciboService,
)
from app.modulos.terceros.services.tarifario_service import TarifarioService

Q = date(2026, 8, 1)
S = date(2026, 8, 16)
SEPT = date(2026, 9, 1)
T = "ARANDA, HUGO"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add_all([Liquidacion(quincena=q) for q in (Q, S, SEPT)])
    sesion.commit()
    yield sesion
    sesion.close()


@pytest.fixture()
def recibos(db):
    return ReciboService(db)


def _liq(db, q):
    return db.query(Liquidacion).filter(Liquidacion.quincena == q).first()


def viaje(db, q=Q, precio="100000", **campos):
    """Un viaje con su tarifa, ya calculado. La tarifa es la del capataz SOSA,
    así un viaje de otro capataz queda sin precio."""
    TarifarioService(db).crear("viajes", q, {"tercero": T, "capataz": "SOSA",
                                             "precio": precio})
    fila = Viaje(liquidacion_id=_liq(db, q).id, **{
        "tercero": T, "cliente": "SAN MIGUEL", "finca": "CASPINCHANGO",
        "capataz": "SOSA", "cantidad_viajes": 1, **campos})
    db.add(fila)
    db.commit()
    CalculoService(db).calcular(q, ("viajes",))
    db.refresh(fila)
    return fila


def viaje_sin_tarifa(db, q=Q):
    fila = Viaje(liquidacion_id=_liq(db, q).id, tercero=T, cliente="OTRO",
                 finca="OTRA", capataz="NADIE", cantidad_viajes=1)
    db.add(fila)
    db.commit()
    CalculoService(db).calcular(q, ("viajes",))
    return fila


def repuesto(db, q=Q, monto="30000", **campos):
    fila = Repuesto(liquidacion_id=_liq(db, q).id, tercero=T, maquina="COLECTIVO",
                    repuesto="EMBRAGUE", fecha=q, monto_total=Decimal(monto), **campos)
    db.add(fila)
    db.commit()
    CalculoService(db).calcular(q, ("repuestos",))
    db.refresh(fila)
    return fila


def seguro(db, q=Q, importe="5000"):
    db.add(PrecioSeguro(quincena=q, tercero=T, tipo_seguro="AUTOMOTOR",
                        sujeto="COLECTIVO FAP480", importe=Decimal(importe)))
    db.commit()


def detalle(recibos, q=Q):
    return recibos.detalle(q, T)


# ─── Los bloques ────────────────────────────────────────────────────────────

def test_los_seguros_van_aparte_y_no_entran_al_total_a_facturar(db, recibos):
    viaje(db)
    seguro(db)
    d = detalle(recibos)
    assert d["total_a_facturar"] == Decimal("100000.00")
    assert d["seguros"] == Decimal("5000.00")
    assert d["total_a_pagar"] == Decimal("95000.00")
    assert [g["concepto"] for g in d["contenido"]["seguros"]] == ["seguros"]


def test_lo_que_se_descuenta_resta(db, recibos):
    viaje(db)
    repuesto(db, monto="30000")
    assert detalle(recibos)["total_a_facturar"] == Decimal("70000.00")


def test_lo_movido_va_como_ajuste_y_las_cuotas_aparte(db, recibos):
    """Para que el tercero sepa de qué es cada cosa: esta quincena, cuotas de
    repuestos, y ajustes de otras quincenas con su motivo."""
    viaje(db, q=S)
    llego_tarde = viaje(db, q=Q)
    DestinoService(db).mover("viajes", llego_tarde.id, S, "llegó tarde")
    r = repuesto(db, q=S, monto="60000")
    DestinoService(db).repartir_en_cuotas(r.id, S, 2)

    c = detalle(recibos, S)["contenido"]
    assert [g["label"] for g in c["quincena"]] == ["Viajes"]
    assert [g["label"] for g in c["ajustes"]] == ["Ajuste viajes"]
    assert c["ajustes"][0]["lineas"][0]["motivo"] == "llegó tarde"
    assert [(g["label"], g["lineas"][0]["cuota"]) for g in c["cuotas"]] == [
        ("Repuestos", "1 de 2")]


def test_el_recibo_da_lo_mismo_que_el_calculo(db, recibos):
    """Es el mismo número armado de dos formas: si no coinciden, uno de los
    dos está mal."""
    viaje(db)
    repuesto(db)
    seguro(db)
    fila = next(f for f in CalculoService(db).totales(Q) if f["tercero"] == T)
    d = detalle(recibos)
    assert d["total_a_facturar"] == fila["total_a_facturar"]
    assert d["total_a_pagar"] == fila["total_a_pagar"]


# ─── Emitir congela ─────────────────────────────────────────────────────────

def test_emitido_no_cambia_aunque_cambie_la_tarifa(db, recibos):
    viaje(db, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")

    regla = TarifarioService(db).listar("viajes", Q)[0]
    TarifarioService(db).actualizar("viajes", regla.id, {"precio": "130000"})
    CalculoService(db).calcular(Q)

    d = detalle(recibos)
    assert d["emitido"] is True
    assert d["total_a_facturar"] == Decimal("100000.00")
    # Y avisa cuánto daría hoy, para que se note.
    assert d["cambio_desde_emision"] == Decimal("30000.00")


def test_con_lineas_sin_precio_no_se_emite(db, recibos):
    """Emitir sería mandar un recibo incompleto como si estuviera completo."""
    viaje(db)
    viaje_sin_tarifa(db)
    with pytest.raises(ReciboInvalido, match="sin precio"):
        recibos.emitir(Q, T, "La Asturiana")


def test_lo_que_no_se_cobra_no_frena_la_emision(db, recibos):
    viaje(db)
    repuesto(db, no_cobrar=True)
    recibos.emitir(Q, T, "La Asturiana")
    assert detalle(recibos)["total_a_facturar"] == Decimal("100000.00")


def test_la_empresa_es_de_la_lista(db, recibos):
    viaje(db)
    with pytest.raises(ReciboInvalido):
        recibos.emitir(Q, T, "Otra SRL")


def test_no_se_emite_dos_veces(db, recibos):
    viaje(db)
    recibos.emitir(Q, T, "Pamplona")
    with pytest.raises(ReciboInvalido):
        recibos.emitir(Q, T, "Pamplona")


def test_la_empresa_cambia_de_una_quincena_a_otra(db, recibos):
    viaje(db, q=Q)
    viaje(db, q=S)
    recibos.emitir(Q, T, "Pamplona")
    recibos.emitir(S, T, "Baleares")
    assert (factura(detalle(recibos, Q))["empresa"],
            factura(detalle(recibos, S))["empresa"]) == ("Pamplona", "Baleares")


def test_reabrir_pide_motivo_y_vuelve_a_vivo(db, recibos):
    viaje(db, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(ReciboInvalido):
        recibos.reabrir(Q, T, " ")

    regla = TarifarioService(db).listar("viajes", Q)[0]
    TarifarioService(db).actualizar("viajes", regla.id, {"precio": "130000"})
    CalculoService(db).calcular(Q)
    recibos.reabrir(Q, T, "faltaba el aumento")

    d = detalle(recibos)
    assert d["emitido"] is False
    assert d["total_a_facturar"] == Decimal("130000.00")


def test_un_recibo_pagado_no_se_reabre(db, recibos):
    """Cambiaría un saldo que ya se saldó."""
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_pago(Q, T, PAGO_TOTAL)
    with pytest.raises(ReciboInvalido, match="pago"):
        recibos.reabrir(Q, T, "x")


def test_reabrir_deja_la_factura_por_aprobar(db, recibos):
    """Se aprobó contra montos que pueden cambiar."""
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_factura(Q, T, "0001-00000123", Q, "100000")
    recibos.aprobar_factura(Q, T)
    recibos.reabrir(Q, T, "corrección")
    assert factura(detalle(recibos))["estado"] == FACTURA_RECIBIDA


def test_cada_cosa_deja_su_evento(db, recibos):
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana", usuario_id=None)
    recibos.reabrir(Q, T, "faltaba algo")
    recibos.emitir(Q, T, "La Asturiana")
    assert [e.tipo for e in db.query(ReciboEvento).order_by(ReciboEvento.id)] == [
        "EMITIDO", "REABIERTO", "EMITIDO"]
    assert [e["tipo"] for e in detalle(recibos)["eventos"]] == [
        "EMITIDO", "REABIERTO", "EMITIDO"]


# ─── Nada de un recibo emitido se mueve ─────────────────────────────────────

def test_no_se_mueve_una_linea_de_un_recibo_emitido(db, recibos):
    """Quedaría en la foto congelada y en el recibo al que se la mande."""
    v = viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(DestinoInvalido, match="emitida"):
        DestinoService(db).mover("viajes", v.id, S, "llegó tarde")


def test_no_se_mueve_hacia_un_recibo_emitido(db, recibos):
    viaje(db, q=S)
    recibos.emitir(S, T, "La Asturiana")
    v = viaje(db, q=Q)
    with pytest.raises(DestinoInvalido, match="emitida"):
        DestinoService(db).mover("viajes", v.id, S, "llegó tarde")


def test_no_se_reparte_en_cuotas_sobre_un_recibo_emitido(db, recibos):
    viaje(db, q=S)
    recibos.emitir(S, T, "La Asturiana")
    r = repuesto(db, q=Q)
    with pytest.raises(DestinoInvalido, match="emitida"):
        DestinoService(db).repartir_en_cuotas(r.id, Q, 3)


# ─── La factura ─────────────────────────────────────────────────────────────

def factura(d: dict) -> dict:
    """La factura de una orden que se le factura entera a una sola empresa."""
    assert len(d["facturas"]) == 1
    return d["facturas"][0]


def test_la_factura_se_registra_sobre_un_recibo_emitido(db, recibos):
    viaje(db)
    with pytest.raises(ReciboInvalido, match="no está emitida"):
        recibos.registrar_factura(Q, T, "0001-00000123", Q, "100000")


def test_la_factura_avisa_si_no_coincide_con_el_total_a_facturar(db, recibos):
    viaje(db)
    seguro(db)
    recibos.emitir(Q, T, "La Asturiana")
    # Facturó con el seguro adentro: es el error que el recibo quiere evitar.
    recibos.registrar_factura(Q, T, "0001-00000123", Q, "95000")
    assert factura(detalle(recibos))["coincide"] is False
    recibos.registrar_factura(Q, T, "0001-00000124", Q, "100000")
    assert factura(detalle(recibos))["coincide"] is True


def test_rechazar_pide_motivo_y_la_corregida_vuelve_a_recibida(db, recibos):
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_factura(Q, T, "0001-00000123", Q, "95000")
    with pytest.raises(ReciboInvalido):
        recibos.rechazar_factura(Q, T, "")
    recibos.rechazar_factura(Q, T, "facturó con el seguro adentro")
    assert factura(detalle(recibos))["estado"] == FACTURA_RECHAZADA

    recibos.registrar_factura(Q, T, "0001-00000124", Q, "100000")
    f = factura(detalle(recibos))
    assert f["estado"] == FACTURA_RECIBIDA and f["motivo"] is None


def test_una_factura_aprobada_no_se_reemplaza(db, recibos):
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_factura(Q, T, "0001-00000123", Q, "100000")
    recibos.aprobar_factura(Q, T)
    assert factura(detalle(recibos))["estado"] == FACTURA_APROBADA
    with pytest.raises(ReciboInvalido):
        recibos.registrar_factura(Q, T, "0001-00000999", Q, "1")


# ─── El pago y el saldo ─────────────────────────────────────────────────────

def test_sin_pago_lo_que_se_debia_pasa_a_la_quincena_siguiente(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    viaje(db, q=S, precio="80000")
    d = detalle(recibos, S)
    assert d["saldo_anterior"] == Decimal("100000.00")
    assert d["total"] == Decimal("180000.00")


def test_pagado_entero_deja_el_saldo_en_cero(db, recibos):
    viaje(db, q=Q)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_pago(Q, T, PAGO_TOTAL)
    viaje(db, q=S)
    assert detalle(recibos, S)["saldo_anterior"] == Decimal("0.00")


def test_pagado_entero_incluye_el_saldo_anterior(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    viaje(db, q=S, precio="80000")
    recibos.emitir(S, T, "La Asturiana")
    recibos.registrar_pago(S, T, PAGO_TOTAL)

    assert detalle(recibos, S)["pago_importe"] == Decimal("180000.00")
    viaje(db, q=SEPT)
    assert detalle(recibos, SEPT)["saldo_anterior"] == Decimal("0.00")


def test_no_se_toca_un_pago_anterior_a_otro_ya_registrado(db, recibos):
    """El entero de la 2da ya incluye lo que quedaba de la 1ra: marcar pagada
    también la 1ra contaría dos veces la misma deuda."""
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    viaje(db, q=S, precio="80000")
    recibos.emitir(S, T, "La Asturiana")
    recibos.registrar_pago(S, T, PAGO_TOTAL)
    with pytest.raises(ReciboInvalido, match="ya tiene registrado el pago"):
        recibos.registrar_pago(Q, T, PAGO_TOTAL)

def test_un_pago_parcial_deja_la_diferencia(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(ReciboInvalido):
        recibos.registrar_pago(Q, T, PAGO_PARCIAL)
    recibos.registrar_pago(Q, T, PAGO_PARCIAL, importe="60000")
    viaje(db, q=S)
    assert detalle(recibos, S)["saldo_anterior"] == Decimal("40000.00")


def test_sacar_el_pago_vuelve_a_dejar_la_deuda(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    recibos.registrar_pago(Q, T, PAGO_TOTAL)
    recibos.registrar_pago(Q, T, None)
    viaje(db, q=S)
    assert detalle(recibos, S)["saldo_anterior"] == Decimal("100000.00")


def test_si_debe_el_tercero_el_saldo_es_negativo(db, recibos):
    """Un tercero que cargó más combustible del que trabajó queda debiendo."""
    repuesto(db, q=Q, monto="50000")
    recibos.emitir(Q, T, "La Asturiana")
    viaje(db, q=S, precio="80000")
    d = detalle(recibos, S)
    assert d["saldo_anterior"] == Decimal("-50000.00")
    assert d["total"] == Decimal("30000.00")


def test_una_quincena_en_revision_no_suma_al_saldo(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(ReciboInvalido):
        recibos.marcar_revision(Q, T, True)
    recibos.marcar_revision(Q, T, True, "discute dos viajes")
    viaje(db, q=S)
    assert detalle(recibos, S)["saldo_anterior"] == Decimal("0.00")


# ─── El saldo inicial ───────────────────────────────────────────────────────

def test_el_saldo_inicial_arranca_la_cuenta(db, recibos):
    recibos.cargar_saldo_inicial(T, S, "25000", "saldo del Excel a 08-1Q")
    viaje(db, q=S, precio="80000")
    d = detalle(recibos, S)
    assert d["saldo_anterior"] == Decimal("25000.00")
    assert d["total"] == Decimal("105000.00")


def test_lo_de_antes_del_saldo_inicial_ya_esta_adentro_de_ese_numero(db, recibos):
    viaje(db, q=Q, precio="100000")
    recibos.emitir(Q, T, "La Asturiana")
    recibos.cargar_saldo_inicial(T, S, "25000")
    viaje(db, q=S)
    assert detalle(recibos, S)["saldo_anterior"] == Decimal("25000.00")


def test_no_cuenta_para_quincenas_anteriores_a_el(db, recibos):
    recibos.cargar_saldo_inicial(T, S, "25000")
    viaje(db, q=Q)
    assert detalle(recibos, Q)["saldo_anterior"] == Decimal("0.00")


def test_el_saldo_inicial_no_se_cambia_despues_de_usarlo(db, recibos):
    recibos.cargar_saldo_inicial(T, Q, "25000")
    viaje(db, q=Q)
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(ReciboInvalido, match="ya se usó"):
        recibos.cargar_saldo_inicial(T, Q, "30000")


# ─── La lista de la quincena ────────────────────────────────────────────────

def test_la_lista_trae_un_renglon_por_tercero(db, recibos):
    viaje(db)
    db.add(Viaje(liquidacion_id=_liq(db, Q).id, tercero="OTRO, DUEÑO",
                 cliente="SAN MIGUEL", finca="CASPINCHANGO", capataz="SOSA",
                 cantidad_viajes=1))
    db.commit()
    TarifarioService(db).crear("viajes", Q, {"tercero": "OTRO, DUEÑO", "precio": "50000"})
    CalculoService(db).calcular(Q)
    recibos.emitir(Q, T, "La Asturiana")

    lista = {r["tercero"]: r for r in recibos.listar(Q)}
    assert set(lista) == {T, "OTRO, DUEÑO"}
    assert lista[T]["emitido"] is True
    assert lista["OTRO, DUEÑO"]["emitido"] is False
    assert lista["OTRO, DUEÑO"]["total_a_facturar"] == Decimal("50000.00")
