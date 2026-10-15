"""Una orden de facturación repartida entre varias empresas.

A algunos terceros se les pide que facturen una parte a una empresa y el resto a
otra (lo pidió el usuario, 2026-10-05). La orden sigue siendo una; lo que pasa a
ser varias es la factura.

Lo que cuidan estos tests es que **lo repartido sume el Total a facturar** antes
de mandarlo, y que la factura de una empresa no se mezcle con la de otra.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base
from app.main import app
from app.modulos.terceros.api import terceros as api
from app.modulos.terceros.models import (
    FACTURA_APROBADA, FACTURA_RECIBIDA, Liquidacion, ReciboEvento, Viaje,
)
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.recibo_service import (
    ReciboInvalido, ReciboService,
)
from app.modulos.terceros.services.tarifario_service import TarifarioService
from tests.roles_de_prueba import usuario_con

Q = date(2026, 8, 1)
T = "ARANDA, HUGO"
DOS = [{"empresa": "La Asturiana", "importe": "70000"},
       {"empresa": "La Sevilla", "importe": "30000"}]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add(Liquidacion(quincena=Q))
    sesion.commit()
    TarifarioService(sesion).crear("viajes", Q, {"tercero": T, "precio": "100000"})
    yield sesion
    sesion.close()


@pytest.fixture()
def recibos(db):
    return ReciboService(db)


def viaje(db):
    """Un viaje de $100.000 más para el tercero."""
    liq = db.query(Liquidacion).filter(Liquidacion.quincena == Q).first()
    db.add(Viaje(liquidacion_id=liq.id, tercero=T, cliente="SAN MIGUEL",
                 finca="CASPINCHANGO", capataz="SOSA", cantidad_viajes=1))
    db.commit()
    CalculoService(db).calcular(Q, ("viajes",))


def reparto(r: dict) -> list[tuple[str, Decimal | None]]:
    return [(f["empresa"], f["importe"]) for f in r["facturas"]]


# ─── Repartir ───────────────────────────────────────────────────────────────

def test_el_reparto_queda_en_el_borrador(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, DOS)
    assert reparto(recibos.detalle(Q, T)) == [
        ("La Asturiana", Decimal("70000.00")), ("La Sevilla", Decimal("30000.00"))]


def test_con_una_sola_empresa_el_importe_sigue_al_total_hasta_emitir(db, recibos):
    """Mientras la orden está abierta el total puede cambiar, y lo que se le
    factura a una sola empresa es todo."""
    viaje(db)
    recibos.elegir_empresa(Q, T, "La Asturiana")
    assert reparto(recibos.detalle(Q, T)) == [("La Asturiana", Decimal("100000.00"))]
    viaje(db)
    assert reparto(recibos.detalle(Q, T)) == [("La Asturiana", Decimal("200000.00"))]

    recibos.emitir(Q, T)
    viaje(db)
    assert reparto(recibos.detalle(Q, T)) == [("La Asturiana", Decimal("200000.00"))]


@pytest.mark.parametrize("partes, motivo", [
    ([{"empresa": "La Asturiana", "importe": "1"}, {"empresa": "La Asturiana", "importe": "2"}],
     "dos veces"),
    ([{"empresa": "La Asturiana", "importe": "70000"}, {"empresa": "La Sevilla"}],
     "Falta cuánto"),
    ([{"empresa": "La Asturiana", "importe": "70000"}, {"empresa": "La Sevilla", "importe": "0"}],
     "Falta cuánto"),
    ([{"empresa": "Otra SRL"}], "tiene que ser una de"),
])
def test_un_reparto_mal_armado_no_se_guarda(db, recibos, partes, motivo):
    viaje(db)
    with pytest.raises(ReciboInvalido, match=motivo):
        recibos.repartir(Q, T, partes)
    assert recibos.detalle(Q, T)["facturas"] == []


def test_cambiar_el_reparto_reemplaza_el_anterior(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, DOS)
    recibos.repartir(Q, T, [{"empresa": "Pamplona", "importe": "60000"},
                            {"empresa": "La Sevilla", "importe": "40000"}])
    assert reparto(recibos.detalle(Q, T)) == [
        ("Pamplona", Decimal("60000.00")), ("La Sevilla", Decimal("40000.00"))]


# ─── Emitir ─────────────────────────────────────────────────────────────────

def test_no_se_emite_si_lo_repartido_no_da_el_total(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, [{"empresa": "La Asturiana", "importe": "70000"},
                            {"empresa": "La Sevilla", "importe": "20000"}])
    with pytest.raises(ReciboInvalido, match=r"\$ 90\.000,00.*\$ 100\.000,00"):
        recibos.emitir(Q, T)
    assert recibos.detalle(Q, T)["emitido"] is False


def test_sin_empresa_elegida_no_se_emite(db, recibos):
    viaje(db)
    with pytest.raises(ReciboInvalido, match="Falta elegir a qué empresa"):
        recibos.emitir(Q, T)


def test_se_emite_cuando_suma_el_total_y_queda_en_la_historia(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, DOS)
    recibos.emitir(Q, T)
    assert recibos.detalle(Q, T)["emitido"] is True
    emitido = db.query(ReciboEvento).filter(ReciboEvento.tipo == "EMITIDO").one()
    assert emitido.detalle["empresas"] == [
        {"empresa": "La Asturiana", "importe": "70000.00"},
        {"empresa": "La Sevilla", "importe": "30000.00"}]


def test_emitir_con_una_empresa_reemplaza_el_reparto(db, recibos):
    """Es lo que hace emitir en lote: todo a la empresa elegida ahí."""
    viaje(db)
    recibos.repartir(Q, T, DOS)
    recibos.emitir(Q, T, "Baleares")
    assert reparto(recibos.detalle(Q, T)) == [("Baleares", Decimal("100000.00"))]


def test_emitida_no_cambia_el_reparto_y_reabierta_lo_conserva(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, DOS)
    recibos.emitir(Q, T)
    with pytest.raises(ReciboInvalido, match="reabrirla"):
        recibos.repartir(Q, T, [{"empresa": "Pamplona"}])

    recibos.reabrir(Q, T, "faltaba un viaje")
    assert reparto(recibos.detalle(Q, T)) == [
        ("La Asturiana", Decimal("70000.00")), ("La Sevilla", Decimal("30000.00"))]


# ─── La factura de cada empresa ─────────────────────────────────────────────

@pytest.fixture()
def emitida(db, recibos):
    viaje(db)
    recibos.repartir(Q, T, DOS)
    recibos.emitir(Q, T)
    return recibos


def facturas(recibos) -> dict[str, dict]:
    return {f["empresa"]: f for f in recibos.detalle(Q, T)["facturas"]}


def test_con_dos_empresas_hay_que_decir_de_cual_es_la_factura(emitida):
    with pytest.raises(ReciboInvalido, match="La Asturiana y La Sevilla"):
        emitida.registrar_factura(Q, T, "0001-00000001", Q, "70000")
    with pytest.raises(ReciboInvalido, match="no se le factura a Pamplona"):
        emitida.registrar_factura(Q, T, "0001-00000001", Q, "70000", empresa="Pamplona")


def test_cada_factura_se_compara_con_lo_de_su_empresa(emitida):
    emitida.registrar_factura(Q, T, "0001-00000001", Q, "70000", empresa="La Asturiana")
    emitida.registrar_factura(Q, T, "0001-00000002", Q, "70000", empresa="La Sevilla")
    f = facturas(emitida)
    assert (f["La Asturiana"]["numero"], f["La Asturiana"]["coincide"]) == ("0001-00000001", True)
    assert (f["La Sevilla"]["numero"], f["La Sevilla"]["coincide"]) == ("0001-00000002", False)


def test_aprobar_una_no_aprueba_la_otra(emitida):
    emitida.registrar_factura(Q, T, "0001-00000001", Q, "70000", empresa="La Asturiana")
    emitida.registrar_factura(Q, T, "0001-00000002", Q, "30000", empresa="La Sevilla")
    emitida.aprobar_factura(Q, T, empresa="La Asturiana")
    emitida.rechazar_factura(Q, T, "le falta el CUIT", empresa="La Sevilla")
    f = facturas(emitida)
    assert f["La Asturiana"]["estado"] == FACTURA_APROBADA
    assert (f["La Sevilla"]["estado"], f["La Sevilla"]["motivo"]) == ("RECHAZADA", "le falta el CUIT")


def test_reabrir_deja_por_aprobar_las_aprobadas_y_conserva_los_numeros(emitida):
    emitida.registrar_factura(Q, T, "0001-00000001", Q, "70000", empresa="La Asturiana")
    emitida.aprobar_factura(Q, T, empresa="La Asturiana")
    emitida.reabrir(Q, T, "corrección")
    f = facturas(emitida)
    assert (f["La Asturiana"]["estado"], f["La Asturiana"]["numero"]) == (
        FACTURA_RECIBIDA, "0001-00000001")


# ─── Por la API ─────────────────────────────────────────────────────────────

LIQUIDADOR = usuario_con("Liquidador de terceros")


@pytest.fixture()
def cliente():
    # Una sola conexión para todos los hilos: el TestClient atiende en otro.
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    sesion.add(Liquidacion(quincena=Q))
    sesion.commit()
    TarifarioService(sesion).crear("viajes", Q, {"tercero": T, "precio": "100000"})
    viaje(sesion)
    app.dependency_overrides[get_usuario_actual] = lambda: LIQUIDADOR
    app.dependency_overrides[api.get_recibos] = lambda: ReciboService(sesion)
    yield TestClient(app)
    app.dependency_overrides.clear()
    sesion.close()


def test_la_api_reparte_emite_y_registra_la_factura_de_cada_empresa(cliente):
    base = {"quincena": str(Q), "tercero": T}
    r = cliente.put("/api/terceros/recibos/empresas", json={**base, "empresas": DOS})
    assert r.status_code == 200
    assert [(f["empresa"], f["importe"]) for f in r.json()["facturas"]] == [
        ("La Asturiana", "70000.00"), ("La Sevilla", "30000.00")]

    r = cliente.post("/api/terceros/recibos/emitir",
                     json={"quincena": str(Q), "recibos": [{"tercero": T}]})
    assert r.json()["emitidos"] == [T]

    r = cliente.put("/api/terceros/recibos/factura", json={
        **base, "empresa": "La Sevilla", "numero": "0002-00000010",
        "fecha": "2026-08-20", "importe": "30000"})
    assert r.status_code == 200
    sevilla = next(f for f in r.json()["facturas"] if f["empresa"] == "La Sevilla")
    assert (sevilla["numero"], sevilla["fecha"], sevilla["coincide"]) == (
        "0002-00000010", "2026-08-20", True)

    r = cliente.post("/api/terceros/recibos/factura/aprobar",
                     json={**base, "empresa": "La Sevilla"})
    assert r.status_code == 200
