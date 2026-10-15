"""Los ajustes del recibo y lo que llega tarde a un recibo ya emitido.

Lo que estos tests cuidan es que **nada se pague ni se descuente dos veces** y
que **nada que cambió después de emitir quede sin ver**: lo que llegó tarde se
propone en el recibo abierto, y una vez resuelto deja de aparecer.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CALCULADO, HoraReparacion, Liquidacion, PrecioSeguro, ReciboEvento, Viaje,
)
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.destino_service import (
    DestinoInvalido, DestinoService,
)
from app.modulos.terceros.services.grilla_service import GrillaService
from app.modulos.terceros.services.recibo_service import (
    ReciboInvalido, ReciboService,
)
from app.modulos.terceros.services.tarifario_service import TarifarioService

P = date(2026, 8, 1)     # la quincena que se emite
Q = date(2026, 8, 16)    # la abierta, donde se propone lo tardío
SEPT = date(2026, 9, 1)
T = "ARANDA, HUGO"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add_all([Liquidacion(quincena=q) for q in (P, Q, SEPT)])
    sesion.commit()
    yield sesion
    sesion.close()


@pytest.fixture()
def recibos(db):
    return ReciboService(db)


def _liq(db, q):
    return db.query(Liquidacion).filter(Liquidacion.quincena == q).first()


def tarifa(db, q=P, precio="100000"):
    TarifarioService(db).crear("viajes", q, {"tercero": T, "precio": precio})


def viaje(db, q=P, **campos) -> Viaje:
    fila = Viaje(liquidacion_id=_liq(db, q).id, **{
        "tercero": T, "cliente": "SAN MIGUEL", "finca": "CASPINCHANGO",
        "capataz": "SOSA", "cantidad_viajes": 1, **campos})
    db.add(fila)
    db.commit()
    CalculoService(db).calcular(q, ("viajes",))
    db.refresh(fila)
    return fila


def emitido(db, recibos, q=P):
    """La quincena con un viaje, emitida."""
    tarifa(db, q)
    v = viaje(db, q)
    recibos.emitir(q, T, "La Asturiana")
    return v


def tarde(recibos, q=Q):
    return recibos.llegadas(q).get(T, [])


# ─── El ajuste manual ───────────────────────────────────────────────────────

def test_un_ajuste_positivo_suma_y_uno_negativo_resta(db, recibos):
    tarifa(db)
    viaje(db)
    recibos.crear_ajuste(P, T, "combustible", "20000", "descuento mal hecho")
    recibos.crear_ajuste(P, T, "otro", "-5000", "daño en la finca")
    assert recibos.detalle(P, T)["total_a_facturar"] == Decimal("115000.00")


def test_el_ajuste_va_al_bloque_de_ajustes_agrupado_por_concepto(db, recibos):
    tarifa(db)
    viaje(db)
    recibos.crear_ajuste(P, T, "viajes", "15000", "faltó un medio viaje")
    recibos.crear_ajuste(P, T, "otro", "-5000", "daño en la finca")

    ajustes = recibos.detalle(P, T)["contenido"]["ajustes"]
    assert [(g["label"], g["neto"]) for g in ajustes] == [
        ("Ajuste viajes", "15000.00"), ("Otros ajustes", "-5000.00")]


def test_lo_movido_y_lo_ajustado_del_mismo_concepto_van_juntos(db, recibos):
    """Para el tercero las dos cosas son «un ajuste de viajes», y el total del
    grupo es con el signo de cada línea."""
    tarifa(db)
    tarifa(db, Q)
    viaje(db, Q)
    movido = viaje(db, P)
    DestinoService(db).mover("viajes", movido.id, Q, "llegó tarde")
    recibos.crear_ajuste(Q, T, "viajes", "-30000", "cobró de más un viaje")

    grupo = recibos.detalle(Q, T)["contenido"]["ajustes"]
    assert [(g["label"], g["neto"], len(g["lineas"])) for g in grupo] == [
        ("Ajuste viajes", "70000.00", 2)]


def test_el_ajuste_entra_a_los_totales_del_calculo_y_de_la_portada(db, recibos):
    tarifa(db)
    viaje(db)
    recibos.crear_ajuste(P, T, "otro", "-5000", "daño en la finca")

    fila = next(f for f in CalculoService(db).totales(P) if f["tercero"] == T)
    assert fila["ajustes"] == Decimal("-5000.00")
    assert fila["total_a_facturar"] == recibos.detalle(P, T)["total_a_facturar"]
    portada = CalculoService(db).importes_por_quincena()[P]
    assert portada["ajustes"] == Decimal("-5000.00")
    assert portada["total"] == Decimal("95000.00")


def test_el_ajuste_aparece_en_la_grilla(db, recibos):
    recibos.crear_ajuste(P, T, "combustible", "-2500", "litros de más")
    f = next(f for f in GrillaService(db).lineas(P) if f["concepto"] == "ajustes")
    assert (f["signo"], f["importe"], f["ajuste_de_label"], f["motivo"]) == (
        -1, Decimal("2500.00"), "Combustible", "litros de más")


@pytest.mark.parametrize("concepto, importe, motivo", [
    ("seguros", "100", "x"),       # no es un concepto de ajuste
    ("otro", "0", "x"),            # un ajuste de cero no ajusta nada
    ("otro", "100", "  "),         # sin motivo el tercero no entiende qué es
])
def test_un_ajuste_mal_cargado_se_rechaza(db, recibos, concepto, importe, motivo):
    with pytest.raises(ReciboInvalido):
        recibos.crear_ajuste(P, T, concepto, importe, motivo)


def test_la_quincena_de_origen_es_anterior(db, recibos):
    with pytest.raises(ReciboInvalido):
        recibos.crear_ajuste(P, T, "otro", "100", "x", quincena_origen=Q)


def test_no_se_ajusta_un_recibo_emitido(db, recibos):
    """Lo emitido es una foto: el ajuste va en el recibo abierto."""
    emitido(db, recibos)
    with pytest.raises(ReciboInvalido, match="emitida"):
        recibos.crear_ajuste(P, T, "otro", "100", "x")


def test_un_ajuste_se_corrige_y_se_borra_mientras_no_se_emita(db, recibos):
    tarifa(db)
    viaje(db)
    a = recibos.crear_ajuste(P, T, "otro", "100", "x")
    recibos.editar_ajuste(a.id, "combustible", "-200", "corregido")
    assert recibos.detalle(P, T)["total_a_facturar"] == Decimal("99800.00")

    recibos.emitir(P, T, "La Asturiana")
    with pytest.raises(ReciboInvalido):
        recibos.borrar_ajuste(a.id)
    recibos.reabrir(P, T, "faltaba algo")
    recibos.borrar_ajuste(a.id)
    assert recibos.detalle(P, T)["total_a_facturar"] == Decimal("100000.00")


def test_el_ajuste_queda_en_la_foto_y_en_la_historia(db, recibos):
    tarifa(db)
    viaje(db)
    recibos.crear_ajuste(P, T, "otro", "-5000", "daño en la finca")
    recibos.emitir(P, T, "La Asturiana")

    d = recibos.detalle(P, T)
    assert d["total_a_facturar"] == Decimal("95000.00")
    assert [e.tipo for e in db.query(ReciboEvento).order_by(ReciboEvento.id)] == [
        "AJUSTE", "EMITIDO"]


# ─── Lo que llegó después de emitir ─────────────────────────────────────────

def test_lo_que_llega_despues_de_emitir_se_propone_mover(db, recibos):
    emitido(db, recibos)
    nuevo = viaje(db, P, capataz="OTRO")

    items = tarde(recibos)
    assert [(i["tipo"], i["propuesta"], i["id"], i["diferencia"]) for i in items] == [
        ("llego", "mover", nuevo.id, Decimal("100000.00"))]


def test_moverlo_al_recibo_abierto_lo_resuelve(db, recibos):
    """La traba deja mover lo que no está en la foto: es justamente lo que hay
    que llevar al recibo abierto."""
    emitido(db, recibos)
    nuevo = viaje(db, P, capataz="OTRO")
    DestinoService(db).mover("viajes", nuevo.id, Q, "llegó después de emitir")

    assert tarde(recibos) == []
    ajustes = recibos.detalle(Q, T)["contenido"]["ajustes"]
    assert [(g["label"], g["neto"]) for g in ajustes] == [("Ajuste viajes", "100000.00")]


def test_lo_que_esta_en_la_foto_sigue_sin_poder_moverse(db, recibos):
    v = emitido(db, recibos)
    with pytest.raises(DestinoInvalido, match="emitida"):
        DestinoService(db).mover("viajes", v.id, Q, "x")


def test_lo_que_desaparece_despues_de_emitir_se_propone_ajustar(db, recibos):
    """Un viaje borrado en el origen que ya se le liquidó: se le descuenta en
    el recibo abierto."""
    v = emitido(db, recibos)
    db.delete(v)
    db.commit()
    CalculoService(db).calcular(P)

    items = tarde(recibos)
    assert [(i["tipo"], i["propuesta"], i["diferencia"]) for i in items] == [
        ("desaparecio", "ajuste", Decimal("-100000.00"))]


def test_el_ajuste_por_la_linea_lo_resuelve_y_uno_parcial_deja_el_resto(db, recibos):
    v = emitido(db, recibos)
    db.delete(v)
    db.commit()
    CalculoService(db).calcular(P)
    clave = tarde(recibos)[0]["clave"]

    recibos.crear_ajuste(Q, T, "viajes", "-60000", "viaje borrado", P, clave)
    assert [i["diferencia"] for i in tarde(recibos)] == [Decimal("-40000.00")]
    recibos.crear_ajuste(Q, T, "viajes", "-40000", "el resto", P, clave)
    assert tarde(recibos) == []


def test_un_cambio_de_tarifa_despues_de_emitir_propone_la_diferencia(db, recibos):
    emitido(db, recibos)
    regla = TarifarioService(db).listar("viajes", P)[0]
    TarifarioService(db).actualizar("viajes", regla.id, {"precio": "130000"})
    CalculoService(db).calcular(P)

    items = tarde(recibos)
    assert [(i["tipo"], i["propuesta"], i["diferencia"]) for i in items] == [
        ("cambio", "ajuste", Decimal("30000.00"))]


def test_una_hora_de_taller_aprobada_despues_de_emitir_llega_tarde(db, recibos):
    """Al aprobarse vuelve como línea nueva —el estado es parte de su clave—,
    y se propone cobrarla en el recibo abierto."""
    TarifarioService(db).crear("reparacion", P, {"tercero": T, "precio": "15000"})
    emitido(db, recibos)
    db.add(HoraReparacion(liquidacion_id=_liq(db, P).id, tercero=T, fecha=P,
                          estado="APROBADO", horas_total=Decimal("2")))
    db.commit()
    CalculoService(db).calcular(P)

    items = tarde(recibos)
    assert [(i["concepto"], i["propuesta"], i["diferencia"]) for i in items] == [
        ("reparacion", "mover", Decimal("-30000.00"))]


def test_descartar_pide_motivo_y_deja_de_avisar(db, recibos):
    emitido(db, recibos)
    viaje(db, P, capataz="OTRO")
    clave = tarde(recibos)[0]["clave"]

    with pytest.raises(ReciboInvalido):
        recibos.descartar_llegada(P, T, clave, " ")
    recibos.descartar_llegada(P, T, clave, "viaje de prueba")
    assert tarde(recibos) == []


def test_si_el_recibo_abierto_ya_se_emitio_se_propone_en_el_siguiente(db, recibos):
    emitido(db, recibos)
    tarifa(db, Q)
    viaje(db, Q)
    recibos.emitir(Q, T, "La Asturiana")
    viaje(db, P, capataz="OTRO")

    assert tarde(recibos, Q) == []
    assert len(tarde(recibos, SEPT)) == 1


def test_los_seguros_no_se_comparan(db, recibos):
    """Se cargan a mano en la app, no llegan de un origen."""
    emitido(db, recibos)
    db.add(PrecioSeguro(quincena=P, tercero=T, tipo_seguro="AUTOMOTOR",
                        sujeto="COLECTIVO", importe=Decimal("5000")))
    db.commit()
    CalculoService(db).calcular(P)
    assert tarde(recibos) == []


def test_sin_cambios_despues_de_emitir_no_hay_nada(db, recibos):
    emitido(db, recibos)
    CalculoService(db).calcular(P)
    assert tarde(recibos) == []


def test_la_lista_cuenta_lo_tardio_y_trae_a_quien_solo_tiene_eso(db, recibos):
    emitido(db, recibos)
    viaje(db, P, capataz="OTRO")

    renglon = next(r for r in recibos.listar(Q) if r["tercero"] == T)
    assert renglon["llegadas"] == 1
    assert len(recibos.detalle(Q, T)["llegadas_detalle"]) == 1


# ─── Generar actualiza también la anterior ──────────────────────────────────

def test_generar_actualiza_la_anterior_si_tiene_recibos_emitidos(db, recibos):
    from tests.terceros.test_liquidacion_service import ExternaFalsa, TallerFalso, viaje as fila_origen
    from app.modulos.terceros.api import terceros as api
    from app.modulos.terceros.schemas import GenerarRequest
    from app.modulos.terceros.services.liquidacion_service import LiquidacionService

    usuario = type("U", (), {"id": None})()
    llamadas = []

    class Externa(ExternaFalsa):
        def viajes(self, q):
            llamadas.append(q)
            return [fila_origen(fecha=q.isoformat())]

    servicio = LiquidacionService(db, Externa(), TallerFalso())
    api.generar_liquidacion(GenerarRequest(quincena=P), usuario, servicio, CalculoService(db), recibos)
    TarifarioService(db).crear("viajes", P, {"precio": "100000"})
    CalculoService(db).calcular(P)
    recibos.emitir(P, T, "La Asturiana")

    llamadas.clear()
    salida = api.generar_liquidacion(GenerarRequest(quincena=Q), usuario, servicio,
                                     CalculoService(db), recibos)
    assert llamadas == [Q, P]
    assert salida["anterior"]["quincena"] == P


def test_sin_recibos_emitidos_la_anterior_no_se_toca(db):
    from tests.terceros.test_liquidacion_service import ExternaFalsa, TallerFalso
    from app.modulos.terceros.api import terceros as api
    from app.modulos.terceros.schemas import GenerarRequest
    from app.modulos.terceros.services.liquidacion_service import LiquidacionService

    llamadas = []

    class Externa(ExternaFalsa):
        def viajes(self, q):
            llamadas.append(q)
            return []

    servicio = LiquidacionService(db, Externa(), TallerFalso())
    salida = api.generar_liquidacion(GenerarRequest(quincena=Q),
                                     type("U", (), {"id": None})(), servicio,
                                     CalculoService(db), ReciboService(db))
    assert llamadas == [Q]
    assert salida.get("anterior") is None


def test_si_la_anterior_falla_la_pedida_queda_y_la_anterior_no_cambia(db, recibos):
    """Un origen caído al actualizar la anterior no tira la pedida, y lo que
    la anterior alcanzó a reconciliar antes de fallar no se guarda."""
    import httpx
    from tests.terceros.test_liquidacion_service import (
        ExternaFalsa, TallerFalso, viaje as fila_origen,
    )
    from app.modulos.terceros.api import terceros as api
    from app.modulos.terceros.schemas import GenerarRequest
    from app.modulos.terceros.services.liquidacion_service import LiquidacionService

    usuario = type("U", (), {"id": None})()
    falla = {"activa": False}

    class Externa(ExternaFalsa):
        def viajes(self, q):
            return [fila_origen(fecha=q.isoformat()),
                    *([fila_origen(fecha=q.isoformat(), capataz="NUEVO")]
                      if falla["activa"] and q == P else [])]

        def cargas_combustible(self, q):
            if falla["activa"] and q == P:
                raise httpx.ConnectError("el sistema de campo no contesta")
            return []

    servicio = LiquidacionService(db, Externa(), TallerFalso())
    api.generar_liquidacion(GenerarRequest(quincena=P), usuario, servicio,
                            CalculoService(db), recibos)
    TarifarioService(db).crear("viajes", P, {"precio": "100000"})
    CalculoService(db).calcular(P)
    recibos.emitir(P, T, "La Asturiana")

    falla["activa"] = True
    salida = api.generar_liquidacion(GenerarRequest(quincena=Q), usuario, servicio,
                                     CalculoService(db), recibos)
    assert salida["anterior"]["error"]
    assert db.query(Viaje).filter(Viaje.liquidacion_id == _liq(db, P).id).count() == 1
    assert db.query(Viaje).filter(Viaje.liquidacion_id == _liq(db, Q).id).count() == 1
