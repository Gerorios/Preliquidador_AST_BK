"""Las entradas de escritura que reciben una quincena rechazan con 422 toda fecha
que no sea día 1 o 16. Sin esto, generar con 2026-09-17 creaba una segunda
preliquidación con las mismas líneas que la del 16 (Preliquidacion.quincena es
la fecha cruda; calcular_rango_quincena normalizaba en silencio)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_usuario_actual
from app.core.database import get_db_propia
from app.modulos.preliquidacion.api import preliquidacion as api


class ServiceQueNoDebeLlamarse:
    def generar(self, *a, **k):
        raise AssertionError("el servicio no debe ejecutarse con una quincena inválida")


class DbQueNoDebeUsarse:
    def query(self, *a, **k):
        raise AssertionError("la base no debe tocarse con una quincena inválida")


@pytest.fixture()
def cliente():
    admin = SimpleNamespace(id=1, rol="admin", modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    app.dependency_overrides[api.get_service] = lambda: ServiceQueNoDebeLlamarse()
    app.dependency_overrides[get_db_propia] = lambda: DbQueNoDebeUsarse()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generar_con_dia_17_da_422_y_no_llama_al_servicio(cliente):
    r = cliente.post("/api/preliquidacion/generar", json={"quincena": "2026-09-17"})
    assert r.status_code == 422, r.text
    assert "1 o el 16" in r.text


def test_crear_concepto_con_dia_2_da_422(cliente):
    r = cliente.post("/api/precios/conceptos", json={
        "quincena": "2026-09-02", "tarea_nombre": "COSECHA", "tipo": "PRECIO",
        "unidad_base": "JORNAL", "valor": 100,
    })
    assert r.status_code == 422, r.text
    assert "1 o el 16" in r.text


def test_copiar_con_destino_17_da_422(cliente):
    r = cliente.post("/api/precios/conceptos/copiar",
                     params={"quincena_origen": "2026-09-01", "quincena_destino": "2026-09-17"})
    assert r.status_code == 422, r.text
    assert "1 o el 16" in r.text
