"""JWT con PyJWT en lugar de python-jose, sin cortar las sesiones abiertas.

Los tokens que emitió python-jose (HS256, misma clave) tienen que seguir
valiendo después del cambio: el token de acá se arma a mano, byte a byte, sin
ninguna de las dos librerías, y representa lo que hay hoy en los navegadores."""
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import auth
from app.core.auth import crear_token, invalidar_cache_usuarios, pwd_context
from app.core.config import settings
from app.core.database import Base, get_db_propia
from app.core.models import Usuario
from app.main import app

RAIZ = Path(__file__).resolve().parents[2]


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _token_a_mano(payload: dict, clave: str = None) -> str:
    clave = settings.secret_key if clave is None else clave
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = _b64(json.dumps(payload, separators=(",", ":")).encode())
    firmado = f"{cabecera}.{cuerpo}".encode("ascii")
    firma = _b64(hmac.new(clave.encode(), firmado, hashlib.sha256).digest())
    return f"{cabecera}.{cuerpo}.{firma}"


@pytest.fixture()
def cliente():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Usuario(id=1, nombre="Liq", email="liq@asturiana.com",
                  password=pwd_context.hash("secreta"), rol="admin", activo=True))
    s.commit()
    invalidar_cache_usuarios()
    app.dependency_overrides[get_db_propia] = lambda: s
    yield TestClient(app)
    app.dependency_overrides.clear()
    invalidar_cache_usuarios()
    s.close()


def _me(cliente, token):
    return cliente.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_token_emitido_antes_del_cambio_sigue_valiendo(cliente):
    token = _token_a_mano({"sub": "1", "exp": int(time.time()) + 3600})
    r = _me(cliente, token)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "liq@asturiana.com"


def test_token_expirado_da_401(cliente):
    token = _token_a_mano({"sub": "1", "exp": int(time.time()) - 60})
    r = _me(cliente, token)
    assert r.status_code == 401
    assert r.json()["detail"] == "Sesión inválida o expirada"


def test_token_con_firma_invalida_da_401(cliente):
    token = _token_a_mano({"sub": "1", "exp": int(time.time()) + 3600},
                          clave="otra-clave-que-no-es-la-del-servidor")
    r = _me(cliente, token)
    assert r.status_code == 401
    assert r.json()["detail"] == "Sesión inválida o expirada"


def test_crear_token_lo_acepta_pyjwt_con_sub_string():
    token = crear_token({"sub": 1})
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == "1"


def test_auth_usa_pyjwt_y_no_python_jose():
    # El módulo `jwt` que usa auth es el de PyJWT (con python-jose era
    # `jose.jwt`), y requirements ya no trae python-jose ni alembic (este
    # último nunca se usó: las migraciones son SQL manual).
    assert auth.jwt.__name__ == "jwt"
    assert hasattr(auth.jwt, "PyJWTError")
    reqs = (RAIZ / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pyjwt==" in reqs
    assert "python-jose" not in reqs
    assert "alembic" not in reqs


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_exp_de_crear_token_es_ahora_mas_la_duracion_configurada():
    from datetime import UTC, datetime, timedelta
    token = crear_token({"sub": 1})
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    esperado = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    assert abs(payload["exp"] - esperado.timestamp()) <= 5
