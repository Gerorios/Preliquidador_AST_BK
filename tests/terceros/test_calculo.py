"""El cálculo del neto (etapa 7): elegir la tarifa y sacar el importe.

Lo que estos tests cuidan es que el módulo **no invente un precio** y que **no
pague cero en silencio**: cada línea sin importe tiene que decir por qué, y el
por qué decide a quién hay que ir a buscar.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CALCULADO, NO_APROBADA, NO_COBRAR, SIN_CANTIDAD, SIN_TARIFA, SIN_TERCERO,
    TARIFA_AMBIGUA, UNIDAD_CANTIDAD, UNIDAD_HORA_MAQUINA,
    CargaCombustible, HoraReparacion, HoraServicio, Liquidacion, PrecioSeguro,
    Repuesto, Viaje,
)
from app.modulos.terceros.services.calculo_service import (
    CalculoService, LiquidacionInexistente,
)
from app.modulos.terceros.services.tarifario_service import TarifarioService

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
def calculo(db):
    return CalculoService(db)


@pytest.fixture()
def tarifario(db):
    return TarifarioService(db)


def _liq(db) -> Liquidacion:
    return db.query(Liquidacion).filter(Liquidacion.quincena == Q).first()


def viaje(db, **campos) -> Viaje:
    base = dict(tercero="ARANDA, HUGO", cliente="SAN MIGUEL",
                finca="CASPINCHANGO", capataz="SOSA", cantidad_viajes=1)
    fila = Viaje(liquidacion_id=_liq(db).id, **{**base, **campos})
    db.add(fila)
    db.commit()
    return fila


# ─── La regla más específica ────────────────────────────────────────────────

def test_la_regla_con_mas_dimensiones_le_gana_a_la_general(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "100000"})
    especifica = tarifario.crear("viajes", Q, {
        "tercero": "ARANDA, HUGO", "capataz": "SOSA", "precio": "205000"})
    v = viaje(db)

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == CALCULADO
    assert v.tarifa_id == especifica.id
    assert v.importe == Decimal("205000.00")


def test_una_regla_sin_dimensiones_alcanza_a_cualquier_hecho(db, calculo, tarifario):
    """Una tarifa toda vacía es "a todos igual", y es una carga válida."""
    tarifario.crear("viajes", Q, {"precio": "90000"})
    v = viaje(db, tercero="UN DUEÑO QUE NADIE PACTÓ")

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == CALCULADO
    assert v.importe == Decimal("90000.00")


def test_dos_reglas_igual_de_especificas_dejan_el_hecho_ambiguo(db, calculo, tarifario):
    """El módulo no desempata: elegir mal es cobrar de más sin que nadie vea."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "cliente": "SAN MIGUEL", "precio": "100000"})
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "capataz": "SOSA", "precio": "205000"})
    v = viaje(db)

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == TARIFA_AMBIGUA
    assert v.tarifa_id is None
    assert v.importe == Decimal("0")


def test_una_regla_de_otra_finca_no_alcanza_al_hecho(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "finca": "OTRA FINCA", "precio": "100000"})
    v = viaje(db)

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == SIN_TARIFA


def test_los_espacios_de_mas_y_las_mayusculas_no_rompen_el_cruce(db, calculo, tarifario):
    """El origen manda ' FAP480' y las tarifas se tipean a mano."""
    tarifario.crear("viajes", Q, {"tercero": "aranda,  hugo",
                                  "capataz": "Sosa", "precio": "205000"})
    v = viaje(db, tercero="ARANDA, HUGO ", capataz="SOSA")

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == CALCULADO


# ─── Nada paga cero en silencio ─────────────────────────────────────────────

def test_un_hecho_sin_dueno_no_entra_a_ningun_recibo(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"precio": "90000"})
    v = viaje(db, tercero=None)

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == SIN_TERCERO
    assert v.importe == Decimal("0")


def test_sin_tarifa_el_hecho_no_vale_cero_sino_que_queda_marcado(db, calculo):
    v = viaje(db)
    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == SIN_TARIFA
    assert v.precio_aplicado is None


def test_una_hora_de_taller_no_aprobada_no_se_cobra(db, calculo, tarifario):
    tarifario.crear("reparacion", Q, {"tercero": "ARANDA, HUGO", "precio": "5000"})
    pendiente = HoraReparacion(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                               estado="Pendiente", horas_total=Decimal("3"))
    aprobada = HoraReparacion(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                              estado="Aprobado", horas_total=Decimal("3"))
    db.add_all([pendiente, aprobada])
    db.commit()

    calculo.calcular(Q)
    db.refresh(pendiente), db.refresh(aprobada)
    assert pendiente.estado_calculo == NO_APROBADA
    assert pendiente.importe == Decimal("0")
    assert aprobada.estado_calculo == CALCULADO
    assert aprobada.importe == Decimal("15000.00")


def test_un_repuesto_marcado_no_cobrar_queda_en_cero_con_su_motivo(db, calculo):
    r = Repuesto(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                 monto_total=Decimal("50000"), no_cobrar=True)
    db.add(r)
    db.commit()

    calculo.calcular(Q)
    db.refresh(r)
    assert r.estado_calculo == NO_COBRAR
    assert r.importe == Decimal("0")


def test_el_repuesto_no_se_tarifa_sino_que_trae_su_monto(db, calculo):
    """El precio lo calculó el sistema de compras; el módulo no lo recalcula."""
    r = Repuesto(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                 monto_total=Decimal("48765.4321"))
    db.add(r)
    db.commit()

    calculo.calcular(Q)
    db.refresh(r)
    assert r.estado_calculo == CALCULADO
    assert r.importe == Decimal("48765.43")


def test_un_repuesto_sin_dueno_tampoco_se_cobra(db, calculo):
    r = Repuesto(liquidacion_id=_liq(db).id, tercero=None, monto_total=Decimal("50000"))
    db.add(r)
    db.commit()

    calculo.calcular(Q)
    db.refresh(r)
    assert r.estado_calculo == SIN_TERCERO


def test_una_tarifa_por_cantidad_sobre_una_linea_sin_cantidad_no_paga_cero(db, calculo, tarifario):
    """Una tarea pactada por cantidad sobre una planilla que sólo midió horas.
    Es un tarifario mal armado, y decirlo es distinto de cobrar cero."""
    tarifario.crear("servicio", Q, {"tercero": "ARANDA, HUGO",
                                    "unidad_base": UNIDAD_CANTIDAD, "precio": "1000"})
    h = HoraServicio(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                     planilla="COSECHA", horas_maquina=Decimal("8"), unidades=None)
    db.add(h)
    db.commit()

    calculo.calcular(Q)
    db.refresh(h)
    assert h.estado_calculo == SIN_CANTIDAD
    assert h.importe == Decimal("0")


def test_cantidad_cero_si_es_un_importe_valido(db, calculo, tarifario):
    """Cero viajes son cero pesos, y eso no es un error que haya que resolver."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    v = viaje(db, cantidad_viajes=Decimal("0"))

    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == CALCULADO
    assert v.importe == Decimal("0.00")


# ─── Lo que resuelve la tarifa además del precio ────────────────────────────

def test_el_tipo_de_viaje_lo_dice_la_regla_y_no_el_origen(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "precio": "205000", "tipo_viaje": "LARGO"})
    v = viaje(db)

    calculo.calcular(Q)
    db.refresh(v)
    assert v.tipo_viaje == "LARGO"


def test_la_unidad_base_decide_sobre_que_medida_se_multiplica(db, calculo, tarifario):
    """La fila tiene las dos medidas cargadas: la tarifa elige cuál se paga."""
    tarifario.crear("servicio", Q, {"tercero": "ARANDA, HUGO", "tarea": "COSECHA",
                                    "unidad_base": UNIDAD_HORA_MAQUINA, "precio": "10000"})
    tarifario.crear("servicio", Q, {"tercero": "ARANDA, HUGO", "tarea": "BINS",
                                    "unidad_base": UNIDAD_CANTIDAD, "precio": "500"})
    por_hora = HoraServicio(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                            tarea="COSECHA", horas_maquina=Decimal("8"),
                            unidades=Decimal("40"))
    por_cantidad = HoraServicio(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                                tarea="BINS", horas_maquina=Decimal("8"),
                                unidades=Decimal("40"))
    db.add_all([por_hora, por_cantidad])
    db.commit()

    calculo.calcular(Q)
    db.refresh(por_hora), db.refresh(por_cantidad)
    assert por_hora.unidad_base == UNIDAD_HORA_MAQUINA
    assert por_hora.importe == Decimal("80000.00")      # 8 horas
    assert por_cantidad.unidad_base == UNIDAD_CANTIDAD
    assert por_cantidad.importe == Decimal("20000.00")  # 40 unidades


# ─── Los totales del recibo ─────────────────────────────────────────────────

def test_el_total_a_facturar_no_lleva_los_seguros_y_el_total_a_pagar_si(db, calculo, tarifario):
    """Es la cifra que el Tercero copia en su factura, y el seguro no es algo
    que él venda: es una cuota adelantada que se le recupera al pagarle."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "200000"})
    tarifario.crear("combustible", Q, {"tercero": "ARANDA, HUGO", "precio": "2000"})
    tarifario.crear("seguros", Q, {"tercero": "ARANDA, HUGO", "tipo_seguro": "AUTOMOTOR",
                                   "sujeto": "MERCEDES 1114", "importe": "30000"})
    viaje(db)
    db.add(CargaCombustible(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                            litros=Decimal("25")))
    db.commit()

    calculo.calcular(Q)
    fila = next(f for f in calculo.totales(Q) if f["tercero"] == "ARANDA, HUGO")

    assert fila["viajes"] == Decimal("200000.00")
    assert fila["combustible"] == Decimal("50000.00")
    assert fila["seguros"] == Decimal("30000.00")
    assert fila["total_a_facturar"] == Decimal("150000.00")   # 200.000 − 50.000
    assert fila["total_a_pagar"] == Decimal("120000.00")      # y recién ahí el seguro


def test_un_tercero_con_seguro_y_sin_movimiento_queda_debiendo(db, calculo, tarifario):
    tarifario.crear("seguros", Q, {"tercero": "ROSSI, OSCAR", "tipo_seguro": "AUTOMOTOR",
                                   "sujeto": "FORD F100", "importe": "2000"})
    calculo.calcular(Q)
    fila = next(f for f in calculo.totales(Q) if f["tercero"] == "ROSSI, OSCAR")
    assert fila["total_a_facturar"] == Decimal("0")
    assert fila["total_a_pagar"] == Decimal("-2000")


def test_lo_que_no_esta_calculado_no_entra_a_los_totales(db, calculo, tarifario):
    """Un hecho sin tarifa no suma cero: no suma. Aparece en pendientes."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "200000"})
    viaje(db)
    viaje(db, capataz="OTRO", tercero="SIN PACTAR")

    calculo.calcular(Q)
    totales = {f["tercero"]: f for f in calculo.totales(Q)}
    assert "SIN PACTAR" not in totales
    assert calculo.pendientes(Q)["viajes"] == {SIN_TARIFA: 1}


# ─── Recalcular ─────────────────────────────────────────────────────────────

def test_recalcular_dos_veces_da_lo_mismo(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    viaje(db)

    primero = calculo.calcular(Q)
    segundo = CalculoService(db).calcular(Q)
    assert primero == segundo
    assert segundo["viajes"]["por_estado"] == {CALCULADO: 1}


def test_cargar_la_tarifa_que_faltaba_y_recalcular_corrige_la_linea(db, calculo, tarifario):
    v = viaje(db)
    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == SIN_TARIFA

    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    CalculoService(db).calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == CALCULADO
    assert v.importe == Decimal("205000.00")


def test_calcular_deja_la_marca_de_cuando_se_calculo(db, calculo):
    assert _liq(db).calculada_en is None
    calculo.calcular(Q)
    assert _liq(db).calculada_en is not None


def test_no_se_puede_calcular_una_quincena_que_nadie_genero(calculo):
    with pytest.raises(LiquidacionInexistente) as e:
        calculo.calcular(date(2026, 9, 1))
    assert "Generala antes" in str(e.value)


# ─── La quincena efectiva ───────────────────────────────────────────────────

def test_un_hecho_diferido_paga_los_precios_de_la_quincena_a_la_que_se_fue(db, calculo, tarifario):
    """Si el liquidador lo corrió a la quincena siguiente, cobra con el
    tarifario de esa quincena, no con el de la quincena en que se cargó."""
    siguiente = date(2026, 8, 16)
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "200000"})
    tarifario.crear("viajes", siguiente, {"tercero": "ARANDA, HUGO", "precio": "260000"})
    v = viaje(db, quincena_efectiva=siguiente, motivo_efectiva="llegó tarde")

    calculo.calcular(Q)
    db.refresh(v)
    assert v.importe == Decimal("260000.00")
    # Y no suma en la quincena en que se cargó, sino en aquella en que se cobra.
    assert all(f["tercero"] != "ARANDA, HUGO" for f in calculo.totales(Q))
    assert next(f for f in calculo.totales(siguiente)
                if f["tercero"] == "ARANDA, HUGO")["viajes"] == Decimal("260000.00")


# ─── Cargar un precio ya lo aplica ──────────────────────────────────────────
#
# No hay botón de recalcular: el endpoint que guarda la tarifa recalcula el
# concepto de ese tarifario en el mismo request, como hace Preliquidación con
# sus conceptos. Lo que se prueba acá es lo que ese endpoint llama.

def test_recalcular_un_concepto_no_toca_los_demas(db, calculo, tarifario):
    """Tocar la tarifa de un viaje no puede cambiar lo que vale un repuesto."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    v = viaje(db)
    r = Repuesto(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                 monto_total=Decimal("50000"))
    db.add(r)
    db.commit()

    salida = calculo.calcular(Q, ("viajes",))
    assert list(salida) == ["viajes"]

    db.refresh(v), db.refresh(r)
    assert v.estado_calculo == CALCULADO
    # El repuesto quedó como estaba: nadie lo miró.
    assert r.importe is None


def test_cargar_la_tarifa_deja_la_linea_calculada_sin_pasar_por_nada_mas(db, calculo, tarifario):
    v = viaje(db)
    calculo.calcular(Q)
    db.refresh(v)
    assert v.estado_calculo == SIN_TARIFA

    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    CalculoService(db).recalcular_si_existe(Q, ("viajes",))

    db.refresh(v)
    assert v.estado_calculo == CALCULADO
    assert v.importe == Decimal("205000.00")


def test_borrar_la_tarifa_deja_la_linea_sin_precio_y_no_con_el_viejo(db, calculo, tarifario):
    """Si no se recalculara al borrar, la línea seguiría mostrando un importe
    que ya no se puede explicar con ninguna regla cargada."""
    t = tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    v = viaje(db)
    calculo.calcular(Q)

    tarifario.eliminar("viajes", t.id)
    CalculoService(db).recalcular_si_existe(Q, ("viajes",))

    db.refresh(v)
    assert v.estado_calculo == SIN_TARIFA
    assert v.importe == Decimal("0")
    assert v.precio_aplicado is None


def test_se_puede_pactar_una_tarifa_de_una_quincena_que_no_se_genero(db, tarifario):
    """Sin esto, cargar un precio por adelantado fallaría con un error que no
    tiene nada que ver con el precio."""
    otra = date(2026, 9, 1)
    tarifario.crear("viajes", otra, {"tercero": "ARANDA, HUGO", "precio": "205000"})
    assert CalculoService(db).recalcular_si_existe(otra, ("viajes",)) == {}


def test_la_quincena_de_una_tarifa_se_puede_saber_antes_de_borrarla(tarifario):
    t = tarifario.crear("viajes", Q, {"tercero": "ARANDA", "precio": "100"})
    assert tarifario.quincena_de("viajes", t.id) == Q


# ─── Lo que falta pactar ────────────────────────────────────────────────────

def test_las_combinaciones_salen_con_o_sin_precio(db, calculo, tarifario):
    """De acá salen dos cosas: qué falta pactar y qué valores ofrecerle al
    liquidador cuando carga una regla, para que no los tipee."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "capataz": "SOSA", "precio": "205000"})
    viaje(db)                                  # tiene tarifa
    viaje(db, capataz="OTRO")                  # no la tiene
    viaje(db, capataz="OTRO")                  # la misma combinación otra vez
    calculo.calcular(Q)

    combis = calculo.combinaciones("viajes", Q)
    assert len(combis) == 2
    # De la que más líneas alcanza a la que menos: es el orden en que conviene
    # pactarlas, porque la primera mueve más el recibo.
    assert combis[0]["capataz"] == "OTRO"
    assert combis[0]["lineas"] == 2 and combis[0]["sin_precio"] == 2
    assert combis[1]["capataz"] == "SOSA"
    assert combis[1]["sin_precio"] == 0


def test_la_cantidad_de_una_combinacion_deja_anticipar_el_importe(db, calculo):
    """Antes de pactar, el liquidador quiere saber sobre cuánto se multiplica."""
    viaje(db, cantidad_viajes=Decimal("1"))
    viaje(db, cantidad_viajes=Decimal("0.5"))
    calculo.calcular(Q)

    combi = calculo.combinaciones("viajes", Q)[0]
    assert combi["lineas"] == 2
    assert combi["cantidad"] == Decimal("1.5")


def test_las_horas_de_servicio_se_miden_en_hora_maquina_antes_de_pactar(db, calculo):
    """Sin tarifa no se sabe qué unidad se va a cobrar, y la hora de máquina es
    la que siempre está y la que el liquidador tiene en la cabeza al pactar."""
    db.add(HoraServicio(liquidacion_id=_liq(db).id, tercero="BARRIOS",
                        tarea="BINS", horas_maquina=Decimal("8"),
                        unidades=Decimal("297")))
    db.commit()
    calculo.calcular(Q)

    combi = calculo.combinaciones("servicio", Q)[0]
    assert combi["cantidad"] == Decimal("8")


def test_un_tarifario_sin_hechos_no_tiene_combinaciones(calculo):
    """Los seguros no tienen tabla de hechos: la tarifa es la línea."""
    assert calculo.combinaciones("seguros", Q) == []


# ─── Los importes de la portada ─────────────────────────────────────────────

def test_la_portada_trae_lo_que_suma_cada_rubro_y_el_neto(db, calculo, tarifario):
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "precio": "200000"})
    tarifario.crear("combustible", Q, {"tercero": "ARANDA, HUGO", "precio": "2000"})
    tarifario.crear("seguros", Q, {"tercero": "ARANDA, HUGO", "tipo_seguro": "AUTOMOTOR",
                                   "sujeto": "MERCEDES", "importe": "30000"})
    viaje(db)
    db.add(CargaCombustible(liquidacion_id=_liq(db).id, tercero="ARANDA, HUGO",
                            litros=Decimal("25")))
    db.commit()
    calculo.calcular(Q)

    datos = calculo.importes_por_quincena()[Q]
    assert datos["viajes"] == Decimal("200000.00")
    assert datos["combustible"] == Decimal("50000.00")
    assert datos["seguros"] == Decimal("30000.00")
    # El neto del recibo: lo que se paga menos lo que se descuenta.
    assert datos["total"] == Decimal("120000.00")


def test_lo_que_no_tiene_precio_no_infla_el_total_de_la_portada(db, calculo, tarifario):
    """Una quincena a medio pactar se ve más barata, no más cara: lo que falta
    no suma ni siquiera como cero."""
    tarifario.crear("viajes", Q, {"tercero": "ARANDA, HUGO",
                                  "capataz": "SOSA", "precio": "200000"})
    viaje(db)
    viaje(db, capataz="SIN PACTAR")
    calculo.calcular(Q)

    assert calculo.importes_por_quincena()[Q]["viajes"] == Decimal("200000.00")
