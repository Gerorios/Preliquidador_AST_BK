# /health devuelve sólo el estado y tres booleanos. Los textos de error de las
# conexiones (los de pymysql traen host y puerto de la base) y la lista de
# tablas faltantes van al log, no a la respuesta HTTP.
# El lifespan no corre con TestClient sin `with` (ver test_autorizacion_roles.py),
# así que se simula seteando app.state.tablas_faltantes directamente, y
# verificar_conexiones se reemplaza para no intentar conectar a ninguna base.

import logging

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

TODAS_OK = {"sueldos": True, "externa": True, "propia": True, "errores": []}


@pytest.fixture(autouse=True)
def restaurar_estado():
    yield
    app.state.tablas_faltantes = []


def _conexiones(monkeypatch, resultado):
    monkeypatch.setattr(main, "verificar_conexiones", lambda: resultado)


def test_health_con_conexion_caida_no_expone_el_error(monkeypatch, caplog):
    app.state.tablas_faltantes = []
    _conexiones(monkeypatch, {
        "sueldos": True, "externa": False, "propia": True,
        "errores": ["BD externa: (2003, \"Can't connect to MySQL server on 'db-ficticia.invalid'\")"],
    })

    with caplog.at_level(logging.ERROR):
        r = TestClient(app).get("/health")

    assert r.json() == {"status": "degraded", "bd_sueldos": True,
                        "bd_externa": False, "bd_propia": True}
    assert "db-ficticia.invalid" not in r.text
    assert "Can't connect to MySQL server on 'db-ficticia.invalid'" in caplog.text


def test_health_sin_tablas_faltantes_no_es_error(monkeypatch):
    app.state.tablas_faltantes = []
    _conexiones(monkeypatch, TODAS_OK)

    body = TestClient(app).get("/health").json()

    assert body == {"status": "ok", "bd_sueldos": True,
                    "bd_externa": True, "bd_propia": True}


def test_health_con_tablas_faltantes_devuelve_status_error_sin_listarlas(monkeypatch, caplog):
    app.state.tablas_faltantes = ["usuario_modulo"]
    _conexiones(monkeypatch, TODAS_OK)

    with caplog.at_level(logging.ERROR):
        r = TestClient(app).get("/health")

    assert r.json() == {"status": "error", "bd_sueldos": True,
                        "bd_externa": True, "bd_propia": True}
    assert "usuario_modulo" not in r.text
    assert "usuario_modulo" in caplog.text
