"""Permisos por pantalla (ADR-0020): roles con Ver o Editar por pantalla que se
suman en la persona; el admin pasa todo."""
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_usuario_actual
from app.core.permisos import (
    NIVELES,
    permisos_de,
    puede,
    requiere_admin,
    requiere_pantalla,
)


def _rol(*permisos):
    """Rol simulado: permisos como ('preliquidacion', 'conceptos', 'editar')."""
    return SimpleNamespace(
        permisos=[SimpleNamespace(modulo=m, pantalla=p, nivel=n) for m, p, n in permisos],
    )


def _u(*roles, rol="usuario"):
    return SimpleNamespace(id=1, nombre="T", email="t@t.com", rol=rol, activo=True,
                           roles=list(roles))


def test_niveles():
    assert NIVELES == ("ver", "editar")


def test_permisos_de_arma_el_mapa_por_modulo_y_pantalla():
    u = _u(_rol(("preliquidacion", "gerencial", "ver"),
                ("preliquidacion", "conceptos", "editar"),
                ("terceros", "inicio", "ver")))
    assert permisos_de(u) == {
        "preliquidacion": {"gerencial": "ver", "conceptos": "editar"},
        "terceros": {"inicio": "ver"},
    }


def test_permisos_de_tolera_objetos_sin_roles():
    assert permisos_de(SimpleNamespace(rol="usuario")) == {}
    assert permisos_de(_u()) == {}
    assert permisos_de(SimpleNamespace(rol="usuario", roles=None)) == {}


def test_ver_por_un_rol_y_editar_por_otro_da_editar():
    ver = _rol(("preliquidacion", "verificacion", "ver"))
    editar = _rol(("preliquidacion", "verificacion", "editar"))
    # El orden de los roles no cambia el resultado.
    assert permisos_de(_u(ver, editar)) == {"preliquidacion": {"verificacion": "editar"}}
    assert permisos_de(_u(editar, ver)) == {"preliquidacion": {"verificacion": "editar"}}
    assert puede(_u(ver, editar), "preliquidacion", "verificacion", "editar")


def test_editar_incluye_ver():
    u = _u(_rol(("preliquidacion", "conceptos", "editar")))
    assert puede(u, "preliquidacion", "conceptos")
    assert puede(u, "preliquidacion", "conceptos", "ver")
    assert puede(u, "preliquidacion", "conceptos", "editar")


def test_ver_no_alcanza_para_editar():
    u = _u(_rol(("preliquidacion", "conceptos", "ver")))
    assert puede(u, "preliquidacion", "conceptos", "ver")
    assert not puede(u, "preliquidacion", "conceptos", "editar")


def test_sin_fila_no_hay_acceso():
    u = _u(_rol(("preliquidacion", "conceptos", "editar")))
    assert not puede(u, "preliquidacion", "revision")
    assert not puede(u, "terceros", "conceptos")
    assert not puede(_u(), "preliquidacion", "conceptos")


def test_admin_pasa_todo_sin_permisos():
    admin = _u(rol="admin")
    assert puede(admin, "preliquidacion", "revision", "editar")
    assert puede(admin, "terceros", "inicio", "ver")
    assert puede(admin, "modulo_que_no_existe", "x", "editar")


# --- requiere_pantalla -----------------------------------------------------

ver_listado = requiere_pantalla("preliquidacion", "inicio", "revision")
editar_revision = requiere_pantalla("preliquidacion", "revision", nivel="editar")


@pytest.fixture()
def cliente():
    app = FastAPI()

    @app.get("/listado")
    def listado(usuario=Depends(ver_listado)):
        return {"id": usuario.id}

    @app.post("/revision", dependencies=[Depends(editar_revision)])
    def revision():
        return {"ok": True}

    def con(usuario):
        app.dependency_overrides[get_usuario_actual] = lambda: usuario
        return TestClient(app)
    yield con
    app.dependency_overrides.clear()


def test_requiere_pantalla_admin_pasa_todo(cliente):
    c = cliente(_u(rol="admin"))
    assert c.get("/listado").status_code == 200
    assert c.post("/revision").status_code == 200


def test_requiere_pantalla_con_varias_pantallas_alcanza_una(cliente):
    c = cliente(_u(_rol(("preliquidacion", "revision", "ver"))))
    r = c.get("/listado")
    assert r.status_code == 200
    assert r.json() == {"id": 1}   # devuelve al usuario, para los endpoints que lo usan
    assert cliente(_u(_rol(("preliquidacion", "inicio", "editar")))).get("/listado").status_code == 200


def test_requiere_pantalla_editar_incluye_ver(cliente):
    c = cliente(_u(_rol(("preliquidacion", "revision", "editar"))))
    assert c.get("/listado").status_code == 200
    assert c.post("/revision").status_code == 200


def test_requiere_pantalla_ver_y_editar_de_roles_distintos(cliente):
    c = cliente(_u(_rol(("preliquidacion", "revision", "ver")),
                   _rol(("preliquidacion", "revision", "editar"))))
    assert c.post("/revision").status_code == 200


def test_requiere_pantalla_sin_permiso_responde_403_con_el_texto_de_hoy(cliente):
    for usuario in (
        _u(),                                                   # sin roles
        _u(_rol(("preliquidacion", "revision", "ver"))),        # Ver no alcanza para Editar
        _u(_rol(("terceros", "revision", "editar"))),           # otro módulo
        _u(_rol(("preliquidacion", "conceptos", "editar"))),    # otra pantalla
    ):
        r = cliente(usuario).post("/revision")
        assert r.status_code == 403
        assert r.json()["detail"] == "No tenés permiso para esta operación"
    r = cliente(_u()).get("/listado")
    assert r.status_code == 403
    assert r.json()["detail"] == "No tenés permiso para esta operación"


def test_requiere_pantalla_expone_requisito():
    assert ver_listado.requisito == ("preliquidacion", ("inicio", "revision"), "ver")
    assert editar_revision.requisito == ("preliquidacion", ("revision",), "editar")


def test_requiere_admin_expone_requisito():
    assert requiere_admin().requisito == "admin"


@pytest.mark.parametrize("nivel", ["borrar", "Ver", "", None])
def test_requiere_pantalla_nivel_invalido_falla_al_definir(nivel):
    with pytest.raises(ValueError):
        requiere_pantalla("preliquidacion", "revision", nivel=nivel)


def test_requiere_pantalla_sin_pantallas_falla_al_definir():
    with pytest.raises(ValueError):
        requiere_pantalla("preliquidacion")
