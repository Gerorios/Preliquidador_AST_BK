# Autorización por módulo (ADR-0013): usuarios.rol es global ('admin' ve y
# opera todo); el resto depende de usuario_modulo (rol 'operador' o 'gerente'
# en el módulo). El gerente de preliquidación llega a /api/gerencial y opera
# el maestro de Conceptos completo (/api/precios/conceptos...), porque es
# quien decide los cambios de precios; el resto de lo operativo
# (preliquidación, export) le sigue devolviendo 403. El operador NO accede a
# la vista gerencial (decisión 2026-09-08). La restricción vive en el
# backend (app/core/permisos.py + app/modulos/preliquidacion/permisos.py),
# no en el front.

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db_propia, get_db_externa, get_db_sueldos
from app.core.auth import get_usuario_actual
from app.main import app
from app.modulos.preliquidacion.models import Preliquidacion


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


def _cliente(db, rol: str = "usuario", **modulos: str) -> TestClient:
    usuario = SimpleNamespace(
        id=1, nombre="Test", email="t@t.com", rol=rol, activo=True,
        modulos=[SimpleNamespace(modulo=m, rol=r) for m, r in modulos.items()],
    )
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
    cliente = _cliente(db, preliquidacion="gerente")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 403


def test_gerente_no_exporta_excel(db):
    cliente = _cliente(db, preliquidacion="gerente")
    r = cliente.get("/api/preliquidacion/1/export-excel")
    assert r.status_code == 403


def test_gerente_muta_el_maestro_de_conceptos(db):
    # El gerente decide cambios de precios: opera el maestro de Conceptos
    # completo, igual que admin/jefe. Ninguna de estas debe dar 403 — el
    # status varía según validación de payload/existencia del recurso.
    cliente = _cliente(db, preliquidacion="gerente")
    assert cliente.post("/api/precios/conceptos", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/1", json={}).status_code != 403
    assert cliente.delete("/api/precios/conceptos/1").status_code != 403
    assert cliente.post("/api/precios/conceptos/copiar", json={}).status_code != 403
    assert cliente.patch("/api/precios/conceptos/precio-masivo", json={}).status_code != 403


def test_gerente_ve_el_maestro_en_lectura(db):
    cliente = _cliente(db, preliquidacion="gerente")
    r = cliente.get("/api/precios/conceptos", params={"quincena": "2026-05-01"})
    assert r.status_code == 200


def test_gerente_accede_a_vista_gerencial(db):
    cliente = _cliente(db, preliquidacion="gerente")
    r = cliente.get("/api/gerencial/quincenas")
    assert r.status_code == 200
    assert r.json() == []


# ─── Jefe / admin ─────────────────────────────────────────────────────────────

def test_admin_accede_a_preliquidacion(db):
    cliente = _cliente(db, rol="admin")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 200


def test_operador_accede_a_preliquidacion(db):
    cliente = _cliente(db, preliquidacion="operador")
    r = cliente.get("/api/preliquidacion/")
    assert r.status_code == 200


def test_admin_accede_a_vista_gerencial(db):
    cliente = _cliente(db, rol="admin")
    assert cliente.get("/api/gerencial/quincenas").status_code == 200


def test_operador_no_accede_a_vista_gerencial(db):
    # Decisión 2026-09-08: el operador opera la preliquidación pero NO ve
    # el panel gerencial — eso queda reservado a gerente/admin.
    cliente = _cliente(db, preliquidacion="operador")
    r = cliente.get("/api/gerencial/quincenas")
    assert r.status_code == 403


def test_gerencial_periodo_invalido_da_400(db):
    cliente = _cliente(db, preliquidacion="gerente")
    r = cliente.get("/api/gerencial/resumen")  # sin quincena ni mes
    assert r.status_code == 400


def test_gerente_ve_controles_de_pago(db):
    # Los controles Plantas/Tancadas vs Jornal se exponen en el router
    # gerencial por quincena (solo lectura, sin el PATCH del valor hora).
    db.add(Preliquidacion(quincena=date(2026, 5, 1), creado_por=1))
    db.commit()
    cliente = _cliente(db, preliquidacion="gerente")
    for ruta in ("control-plantas", "control-tancadas"):
        r = cliente.get(f"/api/gerencial/{ruta}", params={"quincena": "2026-05-01"})
        assert r.status_code == 200, ruta
        assert r.json()["filas"] == []


def test_gerencial_control_quincena_inexistente_da_400(db):
    cliente = _cliente(db, preliquidacion="gerente")
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
    # La lectura del maestro exige solo un token válido (get_usuario_actual),
    # no un módulo — comportamiento idéntico al de antes de esta reforma.
    r = cliente.get("/api/precios/conceptos", params={"quincena": "2026-05-01"})
    assert r.status_code == 200
