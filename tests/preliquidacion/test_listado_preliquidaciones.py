"""GET /api/preliquidacion/ trae el desglose de alertas de cada quincena.

El historial de Inicio muestra cuántas líneas tiene cada quincena por tipo de
alerta. El listado ya calculaba esos conteos en `estadisticas_batch` (dos
consultas para todas las quincenas) pero sólo exponía el total: ahora expone
también `incompletas`, `duplicados`, `posibles_duplicados`, `alerta_legajo` y
`sin_empresa`, sin consultas nuevas y sin cambiar qué cuenta
`lineas_con_alerta`.

Sin base real (SQLite en memoria). Todos los datos son ficticios.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base, get_db_externa, get_db_propia, get_db_sueldos
from app.main import app
from app.modulos.preliquidacion.api import preliquidacion as api
from app.modulos.preliquidacion.models import Preliquidacion, PreliquidacionLinea
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

URL = "/api/preliquidacion/"
Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
CAMPOS_DESGLOSE = ("incompletas", "duplicados", "posibles_duplicados", "alerta_legajo")


@pytest.fixture()
def db():
    # StaticPool + check_same_thread=False: el TestClient ejecuta los
    # endpoints en otro thread y la SQLite in-memory vive por conexión.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def cliente(db):
    admin = SimpleNamespace(
        id=1, nombre="Admin Test", email="admin@test.com", rol="admin",
        activo=True, modulos=[],
    )
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    app.dependency_overrides[get_db_propia] = lambda: db
    app.dependency_overrides[get_db_externa] = lambda: db
    app.dependency_overrides[get_db_sueldos] = lambda: db
    app.dependency_overrides[api.get_service] = lambda: PreliquidacionService(db)
    # Sin `with`: no corre el lifespan (que verifica las conexiones reales).
    yield TestClient(app)
    app.dependency_overrides.clear()


def _preliq(db, quincena):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, empresa="EMPRESA A", es_duplicado=False, alerta_legajo=False,
           linea_incompleta=False, es_posible_duplicado=False):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        empresa_asignada=empresa,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"),
        hsmaquina=Decimal("0"), importe_total=Decimal("100"),
        es_duplicado=es_duplicado, alerta_legajo=alerta_legajo,
        linea_incompleta=linea_incompleta, es_posible_duplicado=es_posible_duplicado,
    )
    db.add(l)
    db.commit()
    return l


def _listado_por_id(cliente):
    r = cliente.get(URL)
    assert r.status_code == 200, r.text
    return {item["id"]: item for item in r.json()}


def test_listado_trae_el_desglose_de_alertas(cliente, db):
    p1 = _preliq(db, Q1)
    _linea(db, p1)
    _linea(db, p1, linea_incompleta=True)
    _linea(db, p1, empresa="EMPRESA B", es_duplicado=True)
    _linea(db, p1, empresa="EMPRESA B", es_duplicado=True, alerta_legajo=True)
    _linea(db, p1, empresa=None, es_posible_duplicado=True)
    _linea(db, p1, empresa=None)

    p2 = _preliq(db, Q2)
    _linea(db, p2, empresa=None, linea_incompleta=True)
    _linea(db, p2, empresa="EMPRESA C", alerta_legajo=True)
    _linea(db, p2, empresa="EMPRESA C", es_posible_duplicado=True)

    items = _listado_por_id(cliente)

    assert {k: items[p1.id][k] for k in (*CAMPOS_DESGLOSE, "sin_empresa")} == {
        "incompletas": 1, "duplicados": 2, "posibles_duplicados": 1,
        "alerta_legajo": 1, "sin_empresa": 2,
    }
    assert {k: items[p2.id][k] for k in (*CAMPOS_DESGLOSE, "sin_empresa")} == {
        "incompletas": 1, "duplicados": 0, "posibles_duplicados": 1,
        "alerta_legajo": 1, "sin_empresa": 1,
    }

    # Los mismos números que `GET /{id}/estadisticas` en las claves comunes.
    svc = PreliquidacionService(db)
    for p in (p1, p2):
        stats = svc.estadisticas(p.id)
        for campo in CAMPOS_DESGLOSE:
            assert items[p.id][campo] == stats[campo], campo
        assert items[p.id]["sin_empresa"] == stats["por_empresa"]["SIN EMPRESA"]["total"]
        # P5: el listado no expone el agrupado completo por empresa.
        assert "por_empresa" not in items[p.id]


def test_listado_no_cambia_lineas_con_alerta(cliente, db):
    p = _preliq(db, Q1)
    _linea(db, p, es_duplicado=True, alerta_legajo=True)
    _linea(db, p, empresa=None)
    _linea(db, p)

    item = _listado_por_id(cliente)[p.id]

    assert item["total_lineas"] == 3
    # La línea duplicada y con alerta de legajo cuenta una sola vez; la que
    # sólo no tiene empresa no es una alerta.
    assert item["lineas_con_alerta"] == 1
    assert item["duplicados"] == 1
    assert item["alerta_legajo"] == 1
    assert item["sin_empresa"] == 1


def test_listado_quincena_sin_lineas_trae_ceros(cliente, db):
    p = _preliq(db, Q1)

    item = _listado_por_id(cliente)[p.id]

    assert item["total_lineas"] == 0
    assert item["lineas_con_alerta"] == 0
    for campo in (*CAMPOS_DESGLOSE, "sin_empresa"):
        assert item[campo] == 0, campo


def test_listado_no_consulta_estadisticas_por_quincena(cliente, db, monkeypatch):
    # Guarda de "sin consultas nuevas": el desglose sale de `estadisticas_batch`,
    # no de una llamada a `estadisticas(id)` por cada quincena.
    for quincena in (Q1, Q2):
        p = _preliq(db, quincena)
        _linea(db, p, es_duplicado=True)

    def _falla(self, preliq_id):
        raise AssertionError("el listado no debe llamar a estadisticas() por quincena")

    monkeypatch.setattr(PreliquidacionService, "estadisticas", _falla)

    r = cliente.get(URL)

    assert r.status_code == 200, r.text
    assert len(r.json()) == 2
