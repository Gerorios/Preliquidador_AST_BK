"""Registro de módulos (ADR-0013, PR 4): un objeto por módulo, el núcleo consume la lista."""
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.core.modulos import ModuloInfo
from app.core.permisos import MODULOS
from app.core.auth import get_usuario_actual
from app.modulos import REGISTRO, activos, claves
from app.main import app


def test_registro_tiene_preliquidacion_activa_y_fletes_inactivo():
    por_clave = {m.clave: m for m in REGISTRO}
    assert por_clave["preliquidacion"].activo is True
    assert por_clave["fletes"].activo is False
    assert all(isinstance(m, ModuloInfo) for m in REGISTRO)


def test_claves_del_registro_coinciden_con_permisos():
    assert set(claves()) == set(MODULOS)


def test_etiquetas_rol_preliquidacion():
    m = {x.clave: x for x in REGISTRO}["preliquidacion"]
    assert m.etiquetas_rol == {"operador": "Preliquidador", "gerente": "Gerente"}
    assert m.panel_gerencial is True


def test_rutas_de_fletes_no_estan_montadas():
    paths = app.openapi()["paths"]
    assert not any(p.startswith("/api/fletes") for p in paths)


def test_endpoint_modulos_devuelve_solo_activos():
    usuario = SimpleNamespace(id=1, nombre="T", email="t@t.com", rol="admin", activo=True, modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    try:
        r = TestClient(app).get("/api/auth/modulos")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    claves_resp = [m["clave"] for m in r.json()]
    assert claves_resp == [m.clave for m in activos()]
    assert "fletes" not in claves_resp
    assert r.json()[0]["etiquetas_rol"]["operador"] == "Preliquidador"
