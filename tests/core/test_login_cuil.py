"""El login acepta CUIL pelado o email real, e informa si la contraseña sigue
siendo la inicial (PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context
from app.core.database import Base, get_db_propia
from app.core.identidad import email_de_cuil
from app.core.models import Usuario
from app.main import app

CUIL = "20111111119"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Usuario(nombre="GOMEZ, JUAN", email=email_de_cuil(CUIL),
                password=pwd_context.hash(CUIL), rol="usuario", activo=True),
        Usuario(nombre="Liq", email="liq@asturiana.com",
                password=pwd_context.hash("secreta"), rol="admin", activo=True),
    ])
    s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()


@pytest.mark.parametrize("usuario_tipeado", [CUIL, "20-11111111-9", "20 11111111 9"])
def test_entra_con_el_cuil_en_cualquier_formato(db, usuario_tipeado):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": usuario_tipeado, "password": CUIL})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["nombre"] == "GOMEZ, JUAN"


def test_entra_con_el_email_sintetico_completo(db):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": email_de_cuil(CUIL), "password": CUIL})
    assert r.status_code == 200


def test_el_mail_real_sigue_funcionando(db):
    r = TestClient(app).post("/api/auth/login",
                             data={"username": "liq@asturiana.com", "password": "secreta"})
    assert r.status_code == 200
    assert r.json()["usuario"]["password_inicial"] is False


def test_avisa_que_la_password_sigue_siendo_la_inicial(db):
    r = TestClient(app).post("/api/auth/login", data={"username": CUIL, "password": CUIL})
    assert r.json()["usuario"]["password_inicial"] is True


def test_password_incorrecta_no_entra(db):
    r = TestClient(app).post("/api/auth/login", data={"username": CUIL, "password": "otra"})
    assert r.status_code == 401
