"""Cada persona puede cambiar su propia contraseña (voluntario, PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import invalidar_cache_usuarios, pwd_context
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
    s.add(Usuario(nombre="GOMEZ, JUAN", email=email_de_cuil(CUIL),
                  password=pwd_context.hash(CUIL), rol="usuario", activo=True))
    s.commit()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()
    # Los ids de esta base en memoria arrancan de nuevo en 1 en cada test:
    # sin esto, el cache de proceso de get_usuario_actual (60s de TTL) puede
    # devolverle a otro archivo de test un Usuario de esta base ya cerrada.
    invalidar_cache_usuarios()


def _headers(c):
    r = c.post("/api/auth/login", data={"username": CUIL, "password": CUIL})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cambia_su_password_y_entra_con_la_nueva(db):
    c = TestClient(app)
    r = c.post("/api/auth/password",
               json={"actual": CUIL, "nueva": "mi-clave-nueva"}, headers=_headers(c))
    assert r.status_code == 200, r.text
    assert c.post("/api/auth/login", data={"username": CUIL, "password": "mi-clave-nueva"}).status_code == 200
    assert c.post("/api/auth/login", data={"username": CUIL, "password": CUIL}).status_code == 401


def test_no_cambia_si_la_actual_es_incorrecta(db):
    c = TestClient(app)
    r = c.post("/api/auth/password",
               json={"actual": "no-es", "nueva": "mi-clave-nueva"}, headers=_headers(c))
    assert r.status_code == 400


def test_rechaza_una_nueva_demasiado_corta(db):
    c = TestClient(app)
    r = c.post("/api/auth/password", json={"actual": CUIL, "nueva": "corta"}, headers=_headers(c))
    assert r.status_code == 422


def test_sin_sesion_no_se_puede_cambiar(db):
    r = TestClient(app).post("/api/auth/password", json={"actual": CUIL, "nueva": "mi-clave-nueva"})
    assert r.status_code == 401
