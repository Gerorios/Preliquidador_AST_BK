"""El módulo en el registro, y quién entra a sus endpoints."""
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.modulos.terceros import MODULO, routers
from tests.roles_de_prueba import rol_de_semilla


def _cliente(usuario):
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    return TestClient(app)


def test_modulo_activo():
    """Se activó en la etapa 2, al tener su primera pantalla real."""
    assert MODULO.clave == "terceros" and MODULO.activo is True


def test_operador_de_terceros_ve_el_estado():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, roles=[rol_de_semilla("Liquidador de terceros")])
    r = _cliente(u).get("/api/terceros/")
    assert r.status_code == 200
    assert r.json()["modulo"] == "terceros"


def test_operador_de_preliquidacion_no_entra_a_terceros():
    u = SimpleNamespace(id=1, rol="usuario", activo=True, roles=[rol_de_semilla("Preliquidador")])
    assert _cliente(u).get("/api/terceros/").status_code == 403
