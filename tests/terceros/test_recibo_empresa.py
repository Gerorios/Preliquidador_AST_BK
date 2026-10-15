"""A quién le factura cada tercero, elegido antes de emitir.

Hasta acá la empresa se elegía recién al emitir y se perdía si se cerraba el
diálogo. Ahora se elige cuando se quiere, queda guardada en el recibo y el
borrador ya la muestra (lo pidió el usuario, 2026-10-05).

Lo que cuidan estos tests es que la elección **quede** y que no se pueda
cambiar a quién factura un recibo ya mandado sin reabrirlo.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base
from app.main import app
from app.modulos.terceros.api import terceros as api
from app.modulos.terceros.models import Liquidacion, Viaje
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.recibo_service import (
    ReciboInvalido, ReciboService,
)
from app.modulos.terceros.services.tarifario_service import TarifarioService
from tests.roles_de_prueba import usuario_con

Q = date(2026, 8, 1)
T = "ARANDA, HUGO"


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
def recibos(db):
    return ReciboService(db)


def viaje(db):
    TarifarioService(db).crear("viajes", Q, {"tercero": T, "precio": "100000"})
    liq = db.query(Liquidacion).filter(Liquidacion.quincena == Q).first()
    db.add(Viaje(liquidacion_id=liq.id, tercero=T, cliente="SAN MIGUEL",
                 finca="CASPINCHANGO", capataz="SOSA", cantidad_viajes=1))
    db.commit()
    CalculoService(db).calcular(Q, ("viajes",))


def empresas(r: dict) -> list[str]:
    return [f["empresa"] for f in r["facturas"]]


def test_la_empresa_elegida_queda_en_el_borrador(db, recibos):
    viaje(db)
    recibos.elegir_empresa(Q, T, "Pamplona")

    r = recibos.detalle(Q, T)
    assert empresas(r) == ["Pamplona"]
    assert r["emitido"] is False
    assert [empresas(f) for f in recibos.listar(Q)] == [["Pamplona"]]


def test_elegir_otra_la_reemplaza_y_vacia_la_saca(db, recibos):
    viaje(db)
    recibos.elegir_empresa(Q, T, "Pamplona")
    recibos.elegir_empresa(Q, T, "Baleares")
    assert empresas(recibos.detalle(Q, T)) == ["Baleares"]

    recibos.elegir_empresa(Q, T, None)
    assert empresas(recibos.detalle(Q, T)) == []


def test_solo_se_elige_de_la_lista_cerrada(db, recibos):
    viaje(db)
    with pytest.raises(ReciboInvalido):
        recibos.elegir_empresa(Q, T, "Una que no existe")


def test_emitido_no_cambia_de_empresa_sin_reabrirlo(db, recibos):
    """Un recibo emitido ya se mandó con esa empresa: cambiarla por debajo
    haría que el papel y el sistema digan cosas distintas."""
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    with pytest.raises(ReciboInvalido):
        recibos.elegir_empresa(Q, T, "Pamplona")
    assert empresas(recibos.detalle(Q, T)) == ["La Asturiana"]


def test_reabierto_conserva_la_empresa_y_se_puede_cambiar(db, recibos):
    viaje(db)
    recibos.emitir(Q, T, "La Asturiana")
    recibos.reabrir(Q, T, "se cargó mal un viaje")
    assert empresas(recibos.detalle(Q, T)) == ["La Asturiana"]

    recibos.elegir_empresa(Q, T, "La Sevilla")
    assert empresas(recibos.detalle(Q, T)) == ["La Sevilla"]


def test_una_quincena_sin_generar_no_guarda_nada(recibos):
    with pytest.raises(ReciboInvalido):
        recibos.elegir_empresa(date(2026, 12, 1), T, "Pamplona")


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
    viaje(sesion)
    app.dependency_overrides[get_usuario_actual] = lambda: LIQUIDADOR
    app.dependency_overrides[api.get_recibos] = lambda: ReciboService(sesion)
    yield TestClient(app)
    app.dependency_overrides.clear()
    sesion.close()


def test_la_api_guarda_la_empresa_y_la_devuelve(cliente):
    r = cliente.put("/api/terceros/recibos/empresas",
                    json={"quincena": str(Q), "tercero": T,
                          "empresas": [{"empresa": "Baleares"}]})
    assert r.status_code == 200
    assert empresas(r.json()) == ["Baleares"]
    lista = cliente.get("/api/terceros/recibos", params={"quincena": str(Q)}).json()
    assert [empresas(f) for f in lista] == [["Baleares"]]


def test_la_api_rechaza_una_empresa_fuera_de_la_lista(cliente):
    r = cliente.put("/api/terceros/recibos/empresas",
                    json={"quincena": str(Q), "tercero": T,
                          "empresas": [{"empresa": "Otra"}]})
    assert r.status_code == 422
