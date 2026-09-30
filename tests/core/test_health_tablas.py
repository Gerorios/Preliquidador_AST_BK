# /health devuelve sólo el estado y tres booleanos. Los textos de error de las
# conexiones (los de pymysql traen host y puerto de la base) y los nombres de
# tablas y columnas faltantes van al banner de arranque y al log, no a la
# respuesta HTTP.
# El lifespan no corre con TestClient sin `with` (ver test_autorizacion_roles.py),
# así que para /health se simula seteando app.state.esquema_incompleto
# directamente, y verificar_conexiones se reemplaza para no intentar conectar a
# ninguna base. El chequeo del arranque se prueba corriendo main.lifespan a mano
# (mismo patrón que test_guardia_base.py) contra una SQLite en memoria.

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import main
from app.core.database import Base
from app.main import app

TODAS_OK = {"sueldos": True, "externa": True, "propia": True, "errores": []}


@pytest.fixture(autouse=True)
def restaurar_estado():
    yield
    app.state.esquema_incompleto = False


def _conexiones(monkeypatch, resultado):
    monkeypatch.setattr(main, "verificar_conexiones", lambda: resultado)


# ─── /health ──────────────────────────────────────────────────────────────────

def test_health_con_conexion_caida_no_expone_el_error(monkeypatch, caplog):
    app.state.esquema_incompleto = False
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


def test_health_con_esquema_completo_no_es_error(monkeypatch):
    app.state.esquema_incompleto = False
    _conexiones(monkeypatch, TODAS_OK)

    body = TestClient(app).get("/health").json()

    assert body == {"status": "ok", "bd_sueldos": True,
                    "bd_externa": True, "bd_propia": True}


def test_health_con_esquema_incompleto_devuelve_status_error_sin_detalle(monkeypatch, caplog):
    app.state.esquema_incompleto = True
    _conexiones(monkeypatch, TODAS_OK)

    with caplog.at_level(logging.ERROR):
        r = TestClient(app).get("/health")

    # Sólo status y los tres booleanos: los nombres están en el banner/log.
    assert r.json() == {"status": "error", "bd_sueldos": True,
                        "bd_externa": True, "bd_propia": True}
    assert "migraciones sin aplicar" in caplog.text


# ─── Chequeo al arrancar ──────────────────────────────────────────────────────

def _correr_lifespan():
    async def correr():
        async with main.lifespan(main.app):
            pass
    asyncio.run(correr())


@pytest.fixture
def base_propia(monkeypatch):
    """Base propia simulada con el esquema completo del modelo; el test le saca
    lo que quiera antes de correr el lifespan."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    monkeypatch.setattr(main, "engine_propia", eng)
    monkeypatch.setattr(main.settings, "db_propia_name", "testing")
    monkeypatch.setattr(main.settings, "permitir_base_produccion", False)
    _conexiones(monkeypatch, TODAS_OK)
    yield eng
    eng.dispose()


def test_arranque_con_esquema_completo_lo_da_por_verificado(base_propia, capsys):
    _correr_lifespan()

    salida = capsys.readouterr().out
    assert "Tablas y columnas BD propia: verificadas" in salida
    assert "ERROR" not in salida
    assert app.state.esquema_incompleto is False


def test_arranque_con_columna_faltante_avisa_y_no_aborta(base_propia, capsys):
    with base_propia.begin() as con:
        con.execute(text("ALTER TABLE usuarios DROP COLUMN nombre"))

    _correr_lifespan()  # no levanta SystemExit ni ninguna otra excepción

    salida = capsys.readouterr().out
    assert ("ERROR: faltan columnas en la base propia (migraciones sin aplicar): "
            "usuarios.nombre") in salida
    assert "verificadas" not in salida
    assert app.state.esquema_incompleto is True


def test_arranque_con_tabla_faltante_avisa_y_no_aborta(base_propia, capsys):
    with base_propia.begin() as con:
        con.execute(text("DROP TABLE usuario_modulo"))

    _correr_lifespan()

    salida = capsys.readouterr().out
    assert ("ERROR: faltan tablas en la base propia (migraciones sin aplicar): "
            "usuario_modulo") in salida
    assert "faltan columnas" not in salida
    assert app.state.esquema_incompleto is True


def test_un_fallo_del_chequeo_no_tumba_el_arranque(base_propia, monkeypatch, capsys, caplog):
    def explota(*_):
        raise RuntimeError("fallo-del-inspector")
    monkeypatch.setattr(main, "comparar_esquema", explota)

    with caplog.at_level(logging.ERROR):
        _correr_lifespan()

    salida = capsys.readouterr().out
    assert "ERROR: no se pudo verificar el esquema de la base propia" in salida
    assert "fallo-del-inspector" in caplog.text
    # No se pudo comparar: no hay evidencia de tabla o columna faltante.
    assert app.state.esquema_incompleto is False
