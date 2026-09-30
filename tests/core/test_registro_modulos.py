"""Registro de módulos (ADR-0013, PR 4): un objeto por módulo, el núcleo consume la lista."""
from pathlib import Path

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.core.modulos import ModuloInfo
from app.core.database import Base
from app.core.permisos import MODULOS
from app.core.auth import get_usuario_actual
from app.modulos import REGISTRO, activos, claves
from app import main as app_main
from app.main import app


def test_los_dos_modulos_estan_en_el_registro():
    por_clave = {m.clave: m for m in REGISTRO}
    assert set(por_clave) == {"preliquidacion", "terceros"}
    assert all(isinstance(m, ModuloInfo) for m in REGISTRO)
    # Terceros se activó en la etapa 2 de su plan, al tener su primera pantalla
    # real. No se afirma acá qué módulo está activo: eso cambia con cada módulo
    # nuevo y lo que importa es que el núcleo monte lo que `activos()` diga,
    # que es lo que prueban los dos tests de abajo.


def test_claves_del_registro_coinciden_con_permisos():
    assert set(claves()) == set(MODULOS)


def test_etiquetas_rol_preliquidacion():
    m = {x.clave: x for x in REGISTRO}["preliquidacion"]
    assert m.etiquetas_rol == {"operador": "Preliquidador", "gerente": "Gerente"}
    assert m.panel_gerencial is True


def test_se_montan_las_rutas_de_los_activos_y_ninguna_de_los_inactivos():
    paths = app.openapi()["paths"]
    prefijos_activos = {f"/api/{m.clave}" for m in activos()}
    inactivos = {f"/api/{m.clave}" for m in REGISTRO if not m.activo}
    for prefijo in prefijos_activos:
        assert any(p.startswith(prefijo) for p in paths), f"{prefijo} no se montó"
    for prefijo in inactivos:
        assert not any(p.startswith(prefijo) for p in paths), f"{prefijo} se montó estando inactivo"


def test_endpoint_modulos_devuelve_solo_activos():
    usuario = SimpleNamespace(id=1, nombre="T", email="t@t.com", rol="admin", activo=True, modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    try:
        r = TestClient(app).get("/api/auth/modulos")
    finally:
        app.dependency_overrides.pop(get_usuario_actual, None)
    assert r.status_code == 200
    claves_resp = [m["clave"] for m in r.json()]
    assert claves_resp == [m.clave for m in activos()]
    assert all(m.clave in claves_resp for m in REGISTRO if m.activo)
    assert all(m.clave not in claves_resp for m in REGISTRO if not m.activo)
    assert r.json()[0]["etiquetas_rol"]["operador"] == "Preliquidador"


def test_modelos_de_activos_registrados():
    assert "usuarios" in Base.metadata.tables
    assert "preliquidacion_linea" in Base.metadata.tables


def test_main_no_importa_modulos_por_nombre():
    contenido = Path(app_main.__file__).read_text(encoding="utf-8")
    assert "app.modulos.preliquidacion" not in contenido
    assert "app.modulos.terceros" not in contenido
