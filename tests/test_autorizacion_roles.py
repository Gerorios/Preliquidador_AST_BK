# Autorización por rol: el gerente llega a /api/gerencial y opera el maestro
# de Conceptos completo (/api/precios/conceptos...), porque es quien decide
# los cambios de precios; el resto de lo operativo (preliquidación, export)
# le sigue devolviendo 403. La restricción vive en el backend
# (requiere_rol / requiere_operativo / requiere_conceptos), no en el front.

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db_propia
from app.api.auth import get_usuario_actual
from app.main import app


@pytest.fixture()
def db():
    # StaticPool + check_same_thread=False: el TestClient ejecuta los
    # endpoints en otro thread y la SQLite in-memory vive por conexión.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _cliente_con_rol(db, rol: str) -> TestClient:
    usuario = SimpleNamespace(id=1, nombre="Test", email="t@t.com", rol=rol, activo=True)
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    app.dependency_overrides[get_db_propia] = lambda: db
    # Sin `with`: no corre el lifespan (que verifica las 3 conexiones reales)
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


# ─── Gerente ──────────────────────────────────────────────────────────────────

def test_gerente_no_accede_a_preliquidacion(db):
    cliente = _cliente_con_rol(db, "gerente")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 403


def test_gerente_no_exporta_excel(db):
    cliente = _cliente_con_rol(db, "gerente")
    r = cliente.get("/api/preliquidacion/1/export-excel")
    assert r.status_code == 403


def test_gerente_muta_el_maestro_de_conceptos(db):
    # El gerente decide cambios de precios: opera el maestro de Conceptos
    # completo, igual que admin/jefe. Ninguna de estas debe dar 403 — el
    # status varía según validación de payload/existencia del recurso.
    cliente = _cliente_con_rol(db, "gerente")
    assert cliente.post("/api/precios/conceptos", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/1", json={}).status_code != 403
    assert cliente.delete("/api/precios/conceptos/1").status_code != 403
    assert cliente.post("/api/precios/conceptos/copiar", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/precio-masivo", json={}).status_code != 403


def test_gerente_ve_el_maestro_en_lectura(db):
    cliente = _cliente_con_rol(db, "gerente")
    r = cliente.get("/api/precios/conceptos", params={"quincena": "2026-05-01"})
    assert r.status_code == 200


def test_gerente_accede_a_vista_gerencial(db):
    cliente = _cliente_con_rol(db, "gerente")
    r = cliente.get("/api/gerencial/quincenas")
    assert r.status_code == 200
    assert r.json() == []


# ─── Jefe / admin ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rol", ["admin", "jefe"])
def test_operativo_accede_a_preliquidacion(db, rol):
    cliente = _cliente_con_rol(db, rol)
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 200


@pytest.mark.parametrize("rol", ["admin", "jefe"])
def test_operativo_accede_a_vista_gerencial(db, rol):
    cliente = _cliente_con_rol(db, rol)
    assert cliente.get("/api/gerencial/quincenas").status_code == 200


def test_gerencial_periodo_invalido_da_400(db):
    cliente = _cliente_con_rol(db, "gerente")
    r = cliente.get("/api/gerencial/resumen")  # sin quincena ni mes
    assert r.status_code == 400


def test_sin_token_da_401(db):
    app.dependency_overrides[get_db_propia] = lambda: db
    cliente = TestClient(app)
    assert cliente.get("/api/gerencial/quincenas").status_code == 401
    assert cliente.get("/api/preliquidacion/").status_code == 401
