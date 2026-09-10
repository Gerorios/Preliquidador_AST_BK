"""Permisos por módulo (ADR-0013): admin global; por módulo, operador o gerente."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.core.permisos import tiene_permiso, modulos_de, requiere_modulo, MODULOS, ROLES_MODULO


def _u(rol="usuario", **modulos):
    """Usuario simulado: modulos como {'preliquidacion': 'operador'}."""
    return SimpleNamespace(
        id=1, nombre="T", email="t@t.com", rol=rol, activo=True,
        modulos=[SimpleNamespace(modulo=m, rol=r) for m, r in modulos.items()],
    )


def test_constantes():
    assert "preliquidacion" in MODULOS
    assert ROLES_MODULO == ("operador", "gerente")


def test_modulos_de_devuelve_mapa():
    assert modulos_de(_u(preliquidacion="operador")) == {"preliquidacion": "operador"}
    assert modulos_de(_u()) == {}


def test_admin_pasa_siempre():
    assert tiene_permiso(_u(rol="admin"), "preliquidacion", "operador")
    assert tiene_permiso(_u(rol="admin"), "terceros", "gerente")


def test_operador_pasa_solo_donde_es_operador():
    u = _u(preliquidacion="operador")
    assert tiene_permiso(u, "preliquidacion", "operador")
    assert tiene_permiso(u, "preliquidacion", "operador", "gerente")
    assert not tiene_permiso(u, "preliquidacion", "gerente")
    assert not tiene_permiso(u, "terceros", "operador")


def test_gerente_no_es_operador():
    u = _u(preliquidacion="gerente")
    assert tiene_permiso(u, "preliquidacion", "gerente")
    assert not tiene_permiso(u, "preliquidacion", "operador")


def test_usuario_sin_modulos_no_pasa():
    assert not tiene_permiso(_u(), "preliquidacion", "operador", "gerente")


@pytest.fixture()
def cliente():
    app = FastAPI()

    @app.get("/operativo", dependencies=[Depends(requiere_modulo("preliquidacion", "operador"))])
    def operativo():
        return {"ok": True}

    @app.get("/gerencial", dependencies=[Depends(requiere_modulo("preliquidacion", "gerente"))])
    def gerencial():
        return {"ok": True}

    def con(usuario):
        app.dependency_overrides[get_usuario_actual] = lambda: usuario
        return TestClient(app)
    yield con
    app.dependency_overrides.clear()


def test_requiere_modulo_operador(cliente):
    c = cliente(_u(preliquidacion="operador"))
    assert c.get("/operativo").status_code == 200
    assert c.get("/gerencial").status_code == 403   # decisión 2026-09-08: el operador no ve Gerencial


def test_requiere_modulo_gerente(cliente):
    c = cliente(_u(preliquidacion="gerente"))
    assert c.get("/operativo").status_code == 403
    assert c.get("/gerencial").status_code == 200


def test_requiere_modulo_admin(cliente):
    c = cliente(_u(rol="admin"))
    assert c.get("/operativo").status_code == 200
    assert c.get("/gerencial").status_code == 200


def test_requiere_modulo_sin_permiso_mensaje(cliente):
    r = cliente(_u()).get("/operativo")
    assert r.status_code == 403
    assert r.json()["detail"] == "No tenés permiso para esta operación"


def test_requiere_admin_deja_pasar_al_admin_y_rechaza_al_resto():
    from fastapi import HTTPException
    from types import SimpleNamespace
    from app.core.permisos import requiere_admin

    dependencia = requiere_admin()

    admin = SimpleNamespace(rol="admin", modulos=[])
    assert dependencia(usuario=admin) is admin

    for rol in ("usuario", None):
        comun = SimpleNamespace(rol=rol, modulos=[])
        try:
            dependencia(usuario=comun)
        except HTTPException as e:
            assert e.status_code == 403
        else:
            raise AssertionError(f"rol {rol!r} no debería pasar requiere_admin")
