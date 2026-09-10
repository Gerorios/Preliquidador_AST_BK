"""Molde del módulo Liquidación Terceros: inactivo en el registro, pero su router funciona si se monta."""
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.modulos.terceros import MODULO, routers


def _cliente(usuario):
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    return TestClient(app)


def test_modulo_inactivo():
    assert MODULO.clave == "terceros" and MODULO.activo is False


def test_operador_de_terceros_ve_el_estado():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, modulos=[SimpleNamespace(modulo="terceros", rol="operador")])
    r = _cliente(u).get("/api/terceros/")
    assert r.status_code == 200
    assert r.json()["modulo"] == "terceros"


def test_operador_de_preliquidacion_no_entra_a_terceros():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, modulos=[SimpleNamespace(modulo="preliquidacion", rol="operador")])
    assert _cliente(u).get("/api/terceros/").status_code == 403
