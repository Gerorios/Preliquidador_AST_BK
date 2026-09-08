# /health devuelve status "error" y la lista de tablas faltantes cuando el
# lifespan detectó migraciones sin aplicar en la base propia. El lifespan no
# corre con TestClient sin `with` (ver test_autorizacion_roles.py), así que
# se simula seteando app.state.tablas_faltantes directamente.

from fastapi.testclient import TestClient

from app.main import app


def test_health_sin_tablas_faltantes_no_es_error():
    app.state.tablas_faltantes = []
    cliente = TestClient(app)
    body = cliente.get("/health").json()
    assert body["tablas_faltantes"] == []
    assert body["status"] != "error"


def test_health_con_tablas_faltantes_devuelve_status_error():
    app.state.tablas_faltantes = ["usuario_modulo"]
    cliente = TestClient(app)
    body = cliente.get("/health").json()
    assert body["status"] == "error"
    assert body["tablas_faltantes"] == ["usuario_modulo"]
