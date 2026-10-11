"""El login y /me devuelven rol global + permisos por pantalla (ADR-0020), sin
el esquema anterior por módulo; usuario inactivo no entra."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.core.database import Base, get_db_propia
from app.core.auth import pwd_context
from app.core.models import Rol, RolPermiso, Usuario
from app.main import app
from tests.roles_de_prueba import SEMILLA


def _rol_de_semilla(nombre):
    """Rol real con los permisos que le da la migración core/002."""
    return Rol(nombre=nombre, permisos=[
        RolPermiso(modulo=m, pantalla=p, nivel=n) for r, m, p, n in SEMILLA if r == nombre
    ])


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    u = Usuario(nombre="Liq", email="liq@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    # Dos roles que se pisan en Conceptos: los permisos se suman en la persona.
    preliquidador, gerente = _rol_de_semilla("Preliquidador"), _rol_de_semilla("Gerente")
    u.roles.extend([preliquidador, gerente])
    a = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    # Un admin con un rol igual recibe permisos vacíos: pasa todo por la marca global.
    a.roles.append(gerente)
    i = Usuario(nombre="Inact", email="inact@t.com", password=pwd_context.hash("x"), rol="usuario", activo=False)
    s.add_all([u, a, i]); s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


def _login(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_devuelve_el_rol_global(db):
    assert _login(TestClient(app), "liq@t.com")["usuario"]["rol"] == "usuario"
    assert _login(TestClient(app), "adm@t.com")["usuario"]["rol"] == "admin"


def test_login_y_me_no_devuelven_modulos(db):
    """El esquema anterior por módulo salió del contrato de sesión (BK2)."""
    c = TestClient(app)
    for email in ("liq@t.com", "adm@t.com"):
        login = _login(c, email)
        assert "modulos" not in login["usuario"]
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
        assert r.status_code == 200
        assert "modulos" not in r.json()


PERMISOS_LIQ = {
    "preliquidacion": {
        "inicio": "editar",
        "revision": "editar",
        "verificacion": "editar",
        "mantenimiento": "editar",
        "conceptos": "editar",
        "gerencial": "ver",
    },
}


def test_login_devuelve_permisos(db):
    usuario = _login(TestClient(app), "liq@t.com")["usuario"]
    assert usuario["permisos"] == PERMISOS_LIQ
    # Los roles de la persona no se devuelven.
    assert "roles" not in usuario


def test_me_devuelve_permisos(db):
    c = TestClient(app)
    token = _login(c, "liq@t.com")["access_token"]
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["permisos"] == PERMISOS_LIQ
    assert "roles" not in body


def test_admin_tiene_permisos_vacios(db):
    c = TestClient(app)
    login = _login(c, "adm@t.com")
    assert login["usuario"]["permisos"] == {}
    r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert r.status_code == 200
    assert r.json()["permisos"] == {}


def test_usuario_inactivo_no_loguea(db):
    r = TestClient(app).post(
        "/api/auth/login", data={"username": "inact@t.com", "password": "x"}
    )
    assert r.status_code == 401
