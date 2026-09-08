"""El login y /me devuelven rol global + modulos; usuario inactivo no entra."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.core.database import Base, get_db_propia
from app.core.auth import pwd_context
from app.core.models import Usuario, UsuarioModulo
from app.main import app


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    u = Usuario(nombre="Liq", email="liq@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    u.modulos.append(UsuarioModulo(modulo="preliquidacion", rol="operador"))
    a = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    i = Usuario(nombre="Inact", email="inact@t.com", password=pwd_context.hash("x"), rol="usuario", activo=False)
    s.add_all([u, a, i]); s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


def _login(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_devuelve_modulos(db):
    c = TestClient(app)
    body = _login(c, "liq@t.com")
    assert body["usuario"]["rol"] == "usuario"
    assert body["usuario"]["modulos"] == {"preliquidacion": "operador"}


def test_login_admin_sin_modulos(db):
    body = _login(TestClient(app), "adm@t.com")
    assert body["usuario"]["rol"] == "admin"
    assert body["usuario"]["modulos"] == {}


def test_me_devuelve_modulos(db):
    c = TestClient(app)
    token = _login(c, "liq@t.com")["access_token"]
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["modulos"] == {"preliquidacion": "operador"}


def test_usuario_inactivo_no_loguea(db):
    r = TestClient(app).post(
        "/api/auth/login", data={"username": "inact@t.com", "password": "x"}
    )
    assert r.status_code == 401
