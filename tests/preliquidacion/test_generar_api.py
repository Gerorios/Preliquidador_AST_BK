"""POST /api/preliquidacion/generar: candado por quincena y error claro cuando
la base externa (ADCP) no responde. Origen: incidente 2026-09-18, la externa
quedó bloqueada 12 min y se acumularon 7 generaciones de la misma quincena."""
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_usuario_actual
from app.modulos.preliquidacion.api import preliquidacion as api
from app.modulos.preliquidacion.services.consulta_externa import ExternaNoDisponible


class ServiceFake:
    """Reemplaza PreliquidacionService: generar() hace lo que le pidamos."""

    def __init__(self, generar):
        self._generar = generar

    def generar(self, quincena, usuario_id):
        return self._generar(quincena, usuario_id)

    def estadisticas(self, pid):
        return {"total_lineas": 0, "incompletas": 0, "duplicados": 0}


@pytest.fixture()
def cliente():
    admin = SimpleNamespace(id=1, rol="admin", modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.clear()
    api._GENERACIONES_EN_CURSO.clear()


def _con_service(fn):
    app.dependency_overrides[api.get_service] = lambda: ServiceFake(fn)


def test_segunda_generacion_de_la_misma_quincena_recibe_409(cliente):
    arranco = threading.Event()
    soltar = threading.Event()

    def generar_lento(quincena, usuario_id):
        arranco.set()
        soltar.wait(timeout=10)
        return {"preliquidacion_id": 1, "insertadas": 0, "eliminadas": 0, "sin_cambios": 0}

    _con_service(generar_lento)
    resultados = {}

    def primera():
        resultados["primera"] = cliente.post(
            "/api/preliquidacion/generar", json={"quincena": "2026-09-01"})

    t = threading.Thread(target=primera)
    t.start()
    assert arranco.wait(timeout=5), "la primera generación no arrancó"

    segunda = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-01"})
    assert segunda.status_code == 409, segunda.text
    assert "en curso" in segunda.json()["detail"].lower()

    # Otra quincena no se bloquea por la primera.
    otra = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-16"})
    assert otra.status_code == 200, otra.text

    soltar.set()
    t.join(timeout=10)
    assert resultados["primera"].status_code == 200, resultados["primera"].text

    # El candado se liberó: vuelve a poder generarse.
    tercera = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-01"})
    assert tercera.status_code == 200, tercera.text


def test_externa_no_disponible_da_503_con_mensaje_claro(cliente):
    def generar_falla(quincena, usuario_id):
        raise ExternaNoDisponible("La base de datos de campo no respondió a tiempo")

    _con_service(generar_falla)
    r = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-01"})
    assert r.status_code == 503, r.text
    assert "base de datos de campo" in r.json()["detail"]


def test_cualquier_endpoint_que_use_la_externa_da_503_si_se_corta(cliente):
    # Sin handler global, precios y gerencial devolvían 500 con el texto crudo
    # de pymysql ("Lost connection to MySQL server").
    from sqlalchemy.exc import OperationalError
    from app.core.database import get_db_externa

    class DbQueCorta:
        def execute(self, *a, **k):
            raise OperationalError("SELECT ...", {}, Exception(
                "(2013, 'Lost connection to MySQL server during query (timed out)')"))

    app.dependency_overrides[get_db_externa] = lambda: DbQueCorta()
    r = cliente.get("/api/precios/maestro/clientes")
    assert r.status_code == 503, r.text
    assert "base de datos de campo" in r.json()["detail"]


def test_el_candado_se_libera_aunque_la_generacion_falle(cliente):
    def generar_falla(quincena, usuario_id):
        raise ValueError("quincena inválida")

    _con_service(generar_falla)
    r = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-01"})
    assert r.status_code == 400
    assert not api._GENERACIONES_EN_CURSO
