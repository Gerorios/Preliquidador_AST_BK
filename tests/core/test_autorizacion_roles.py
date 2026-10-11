# Autorización por pantalla (ADR-0020), con los roles que crea la migración
# core/002 (tests/roles_de_prueba.py, SEMILLA): usuarios.rol es global ('admin'
# ve y opera todo); el resto depende de los roles de la persona. El Gerente ve
# la Vista gerencial y edita Conceptos (es quien decide los cambios de
# precios); lo demás de Preliquidación (listado, export) le devuelve 403. El
# Preliquidador no ve la Vista gerencial (decisión 2026-09-08); desde ADR-0020
# sí llega a /api/gerencial/quincenas, por Conceptos (pregunta 4 del plan).
# La restricción vive en el backend (app/core/permisos.py +
# app/modulos/preliquidacion/permisos.py), no en el front. El mapa completo de
# endpoint a pantalla lo fija tests/preliquidacion/test_mapa_permisos.py.

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db_propia, get_db_externa, get_db_sueldos
from app.core.auth import get_usuario_actual
from app.main import app
from app.modulos.preliquidacion.models import Preliquidacion
from tests.roles_de_prueba import usuario_con


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


def _cliente(db, *roles: str, rol: str = "usuario") -> TestClient:
    usuario = usuario_con(*roles, rol=rol)
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    app.dependency_overrides[get_db_propia] = lambda: db
    # Los controles gerenciales construyen PreliquidacionService, que declara
    # las 3 sesiones aunque solo use db_propia — se apuntan todas a la sqlite.
    app.dependency_overrides[get_db_externa] = lambda: db
    app.dependency_overrides[get_db_sueldos] = lambda: db
    # Sin `with`: no corre el lifespan (que verifica las 3 conexiones reales)
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


# ─── Gerente ──────────────────────────────────────────────────────────────────

def test_gerente_no_accede_a_preliquidacion(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 403


def test_gerente_no_exporta_excel(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/preliquidacion/1/export-excel")
    assert r.status_code == 403


def test_gerente_muta_el_maestro_de_conceptos(db):
    # El gerente decide cambios de precios: opera el maestro de Conceptos
    # completo, igual que admin/operador. Ninguna de estas debe dar 403 — el
    # status varía según validación de payload/existencia del recurso.
    cliente = _cliente(db, "Gerente")
    assert cliente.post("/api/precios/conceptos", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/1", json={}).status_code != 403
    assert cliente.delete("/api/precios/conceptos/1").status_code != 403
    assert cliente.post("/api/precios/conceptos/copiar", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/precio-masivo", json={}).status_code != 403


def test_operador_muta_el_maestro_de_conceptos(db):
    # editar_conceptos = Editar en Conceptos, que tienen el Preliquidador y el
    # Gerente: el Preliquidador también opera el maestro completo.
    cliente = _cliente(db, "Preliquidador")
    assert cliente.post("/api/precios/conceptos", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/1", json={}).status_code != 403
    assert cliente.delete("/api/precios/conceptos/1").status_code != 403
    assert cliente.post("/api/precios/conceptos/copiar", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/precio-masivo", json={}).status_code != 403


def test_gerente_ve_el_maestro_en_lectura(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/precios/conceptos", params={"quincena": "2026-05-01"})
    assert r.status_code == 200


def test_gerente_accede_a_vista_gerencial(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/gerencial/quincenas")
    assert r.status_code == 200
    assert r.json() == []


# ─── Admin / Preliquidador ─────────────────────────────────────────────────────────

def test_admin_accede_a_preliquidacion(db):
    cliente = _cliente(db, rol="admin")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 200


def test_operador_accede_a_preliquidacion(db):
    cliente = _cliente(db, "Preliquidador")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 200


def test_admin_accede_a_vista_gerencial(db):
    cliente = _cliente(db, rol="admin")
    assert cliente.get("/api/gerencial/quincenas").status_code == 200


def test_operador_no_accede_a_vista_gerencial(db):
    # Decisión 2026-09-08: el Preliquidador opera la preliquidación pero NO ve
    # el panel gerencial — eso queda reservado al Gerente y al admin.
    cliente = _cliente(db, "Preliquidador")
    r = cliente.get("/api/gerencial/empresas")
    assert r.status_code == 403
    # Único acceso nuevo de la migración (ADR-0020, pregunta 4 del plan): las
    # quincenas generadas, que Conceptos usa de selector. Ya las ve por
    # GET /api/preliquidacion/.
    assert cliente.get("/api/gerencial/quincenas").status_code == 200


def test_gerencial_periodo_invalido_da_400(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/gerencial/resumen")  # sin quincena ni mes
    assert r.status_code == 400


def test_gerente_ve_controles_de_pago(db):
    # Los controles Plantas/Tancadas vs Jornal se exponen en el router
    # gerencial por quincena (solo lectura, sin el PATCH del valor hora).
    db.add(Preliquidacion(quincena=date(2026, 5, 1), creado_por=1))
    db.commit()
    cliente = _cliente(db, "Gerente")
    for ruta in ("control-plantas", "control-tancadas"):
        r = cliente.get(f"/api/gerencial/{ruta}", params={"quincena": "2026-05-01"})
        assert r.status_code == 200, ruta
        assert r.json()["filas"] == []


def test_gerencial_control_quincena_inexistente_da_400(db):
    cliente = _cliente(db, "Gerente")
    r = cliente.get("/api/gerencial/control-plantas", params={"quincena": "2030-01-01"})
    assert r.status_code == 400


def test_sin_token_da_401(db):
    app.dependency_overrides[get_db_propia] = lambda: db
    cliente = TestClient(app)
    assert cliente.get("/api/gerencial/quincenas").status_code == 401
    assert cliente.get("/api/preliquidacion/").status_code == 401


def test_usuario_sin_modulos_recibe_403_en_todo(db):
    cliente = _cliente(db)
    assert cliente.get("/api/preliquidacion/").status_code == 403
    assert cliente.get("/api/gerencial/quincenas").status_code == 403
    assert cliente.post("/api/precios/conceptos", json={}).status_code == 403
    # Cambio a propósito de ADR-0020: la lectura del maestro pide Ver en
    # Conceptos. Antes alcanzaba con un token válido.
    r = cliente.get("/api/precios/conceptos", params={"quincena": "2026-05-01"})
    assert r.status_code == 403
