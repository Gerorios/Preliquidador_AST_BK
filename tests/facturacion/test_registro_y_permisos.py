"""El módulo Facturación en el registro y sus seis pantallas (plan de la E1, D1).

Las claves de pantalla se guardan en la base (rol_permiso.pantalla) y no
cambian. El orden es el del editor de roles. Sólo `unidad` tiene endpoints en
la E1; las otras cinco se declaran igual para que las claves queden fijas (D2).
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.main import app
from app.modulos import REGISTRO, activos
from app.modulos.facturacion import MODULO
from app.modulos.facturacion.permisos import PANTALLAS

# (clave, nombre, editable), en el orden del editor de roles.
CATALOGO_FACTURACION = [
    ("pendientes", "Pendientes", True),
    ("cruce", "Cruce", False),
    ("comprobantes", "Comprobantes", True),
    ("unidad", "Unidad de medida por defecto", True),
    ("equivalencias", "Equivalencias", True),
    ("panel", "Panel", False),
]


def test_el_modulo_esta_registrado_y_activo():
    assert MODULO.clave == "facturacion"
    assert MODULO.activo is True
    assert MODULO in REGISTRO
    assert MODULO in activos()


def test_las_seis_pantallas_del_catalogo():
    assert [(p.clave, p.nombre, p.editable) for p in PANTALLAS] == CATALOGO_FACTURACION
    assert MODULO.pantallas == PANTALLAS
    assert all(p.requiere == () for p in PANTALLAS)


def test_auth_modulos_publica_las_seis_en_orden():
    usuario = SimpleNamespace(id=1, nombre="T", email="t@t.com", rol="admin", activo=True, modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    try:
        r = TestClient(app).get("/api/auth/modulos")
    finally:
        app.dependency_overrides.pop(get_usuario_actual, None)
    assert r.status_code == 200
    por_clave = {m["clave"]: m for m in r.json()}
    pantallas = por_clave["facturacion"]["pantallas"]
    assert [(p["clave"], p["nombre"], p["editable"]) for p in pantallas] == CATALOGO_FACTURACION
    assert all(p["requiere"] == [] for p in pantallas)
