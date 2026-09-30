"""Manejador global de 500: la persona ve un mensaje genérico con un código
corto, y el detalle (texto de la excepción y traceback) va sólo al log, con el
mismo código para poder encontrarlo en el journal. Antes, cada endpoint
devolvía `str(e)` en el `detail`, y los mensajes de pymysql traen host y
puerto de la base."""
import logging
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_usuario_actual
from app.core.database import get_db_propia, get_db_externa, get_db_sueldos

PREFIJO = "Error interno del sistema. Si se repite, avisá a sistemas con el código "
PATRON = re.compile(re.escape(PREFIJO) + r"([A-Z0-9]{6})$")


class _SesionInerte:
    """Reemplaza las sesiones de externa y sueldos: el endpoint no llega a
    usarlas, y así ningún test construye una sesión contra una base real."""


@pytest.fixture()
def cliente():
    admin = SimpleNamespace(id=1, nombre="Admin", email="a@a.com", rol="admin",
                            activo=True, modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    app.dependency_overrides[get_db_externa] = lambda: _SesionInerte()
    app.dependency_overrides[get_db_sueldos] = lambda: _SesionInerte()
    # raise_server_exceptions=False: Starlette re-lanza la excepción después
    # de mandar la respuesta del handler; sin esto el TestClient la propaga
    # al test en lugar de devolver el 500.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _db_que_falla(mensaje):
    def _falla():
        raise RuntimeError(mensaje)
    return _falla


def test_error_interno_da_500_generico_con_codigo_y_detalle_en_el_log(cliente, caplog):
    app.dependency_overrides[get_db_propia] = _db_que_falla("texto-secreto-de-la-base")

    with caplog.at_level(logging.ERROR):
        r = cliente.get("/api/preliquidacion/")

    assert r.status_code == 500, r.text
    detail = r.json()["detail"]
    m = PATRON.fullmatch(detail)
    assert m, detail
    codigo = m.group(1)
    assert "texto-secreto" not in r.text

    # Un mismo registro une el código con la excepción original (y su
    # traceback): es lo que se busca en el journal con el código del toast.
    registros = [rec for rec in caplog.records
                 if rec.levelno >= logging.ERROR and codigo in rec.getMessage()]
    assert registros, f"no hay registro ERROR con el código {codigo}: {caplog.text}"
    rec = registros[0]
    assert rec.exc_info is not None
    assert "texto-secreto-de-la-base" in str(rec.exc_info[1])
    assert "texto-secreto-de-la-base" in caplog.text


def test_dos_errores_distintos_dan_codigos_distintos(cliente):
    app.dependency_overrides[get_db_propia] = _db_que_falla("error-uno")
    r1 = cliente.get("/api/preliquidacion/")
    app.dependency_overrides[get_db_propia] = _db_que_falla("error-dos")
    r2 = cliente.get("/api/preliquidacion/")

    assert r1.status_code == 500 and r2.status_code == 500
    c1 = PATRON.fullmatch(r1.json()["detail"]).group(1)
    c2 = PATRON.fullmatch(r2.json()["detail"]).group(1)
    assert c1 != c2


# ─── Endpoints sin `except Exception` propio (paso 1.2) ───────────────────────
# Antes, cada endpoint del módulo envolvía todo en `except Exception` y
# devolvía `HTTPException(500, str(e))`, así que el handler global nunca se
# enteraba y el texto crudo llegaba al front.

from app.modulos.preliquidacion.api import preliquidacion as api_preliq  # noqa: E402


class _ServiceQueFalla:
    def __init__(self, exc):
        self._exc = exc

    def dashboard_verificacion(self, preliq_id):
        raise self._exc


def _con_service(exc):
    app.dependency_overrides[api_preliq.get_service] = lambda: _ServiceQueFalla(exc)


def test_endpoint_con_error_inesperado_da_500_generico(cliente):
    _con_service(RuntimeError("detalle-interno"))
    r = cliente.get("/api/preliquidacion/1/dashboard-verificacion")
    assert r.status_code == 500, r.text
    assert PATRON.fullmatch(r.json()["detail"]), r.text
    assert "detalle-interno" not in r.text


def test_endpoint_con_valueerror_sigue_dando_404_con_su_texto(cliente):
    _con_service(ValueError("Preliquidacion 1 no encontrada"))
    r = cliente.get("/api/preliquidacion/1/dashboard-verificacion")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Preliquidacion 1 no encontrada"


def test_endpoint_backfill_conceptos_ya_no_existe(cliente):
    # Llamaba a un método del servicio que no existe (siempre 500) y el front
    # no lo usa: se borró.
    app.dependency_overrides[get_db_propia] = lambda: _SesionInerte()
    r = cliente.post("/api/preliquidacion/1/backfill-conceptos")
    assert r.status_code in (404, 405), r.text
    assert "backfill" not in r.text


def test_crear_concepto_con_error_de_base_da_500_generico_sin_sql(cliente):
    # Antes: `except Exception` alrededor del commit → 400 "No se pudo
    # guardar: <SQL y parámetros>". El único error esperable ahí era el
    # `uq_concepto_unif`, que por la API nunca se dispara (uno de
    # cliente/supervisor siempre es NULL, y cada NULL es distinto en un índice
    # único), así que se sacó el try: un error de base es un 500 genérico.
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    def _commit_que_falla():
        raise IntegrityError(
            "INSERT INTO concepto_liquidacion (quincena, tarea_nombre) VALUES (?, ?)",
            ("2026-05-01", "sql-secreto"),
            Exception("UNIQUE constraint failed: concepto_liquidacion.quincena"),
        )

    db.commit = _commit_que_falla
    app.dependency_overrides[get_db_propia] = lambda: db
    try:
        r = cliente.post("/api/precios/conceptos", json={
            "quincena": "2026-05-01", "tarea_nombre": "COSECHA", "codigo": 461,
            "precio": "10", "confirmar_solapamiento": True,
        })
    finally:
        db.close()

    assert r.status_code == 500, r.text
    assert PATRON.fullmatch(r.json()["detail"]), r.text
    assert "INSERT" not in r.text
    assert "sql-secreto" not in r.text
    assert "concepto_liquidacion" not in r.text
