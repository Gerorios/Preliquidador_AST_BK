"""Los endpoints de la pantalla Unidad de medida por defecto (contrato 2.5 del
plan de la E1): GET /api/facturacion/tareas y PATCH /api/facturacion/tareas/{id}.

La regla vive en el servicio y ya la prueba test_unidad_service. Acá se prueba
lo que agrega la capa HTTP: quién entra, los códigos y la forma de la
respuesta. Se monta app.main.app para que actúe el handler del 503; la tabla
propia es SQLite en memoria y el campo es un doble. Todos los datos son
ficticios.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_usuario_actual
from app.core.database import Base, ExternaNoDisponible, get_db_propia
from app.main import app
from app.modulos.facturacion.api import tareas as api
from app.modulos.facturacion.models import TareaFacturacion
from tests.roles_de_prueba import rol_de_semilla

URL = "/api/facturacion/tareas"
CAIDO = "La base de datos de campo (ADCP) no respondió a tiempo. Reintentá en unos minutos."

CAMPO = [
    {"tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "GRUPO 1"},
    {"tarea_id": 20, "nombre": "TAREA B", "grupo_tarea": None},
    {"tarea_id": 30, "nombre": "TAREA C", "grupo_tarea": "GRUPO 2"},
]


class CampoFalso:
    def obtener_tareas(self):
        return [dict(t) for t in CAMPO]


class CampoCaido:
    def obtener_tareas(self):
        raise ExternaNoDisponible(CAIDO)


def contadora(nivel):
    # Rol local: tests/roles_de_prueba.py no se toca, porque su SEMILLA la
    # fija la migración core/002.
    return SimpleNamespace(
        id=1, nombre="Contadora", email="c@t.com", rol="usuario", activo=True,
        roles=[SimpleNamespace(
            nombre="Contadora de prueba",
            permisos=[SimpleNamespace(modulo="facturacion", pantalla="unidad", nivel=nivel)],
        )],
    )


def preliquidador():
    return SimpleNamespace(
        id=2, nombre="Preliq", email="p@t.com", rol="usuario", activo=True,
        roles=[rol_de_semilla("Preliquidador")],
    )


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
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture()
def cliente(db):
    """Arma el cliente con una persona y un campo; limpia los overrides al terminar."""
    def _armar(usuario, campo=None):
        app.dependency_overrides[get_db_propia] = lambda: db
        app.dependency_overrides[api.get_consulta_externa] = lambda: campo or CampoFalso()
        app.dependency_overrides[get_usuario_actual] = lambda: usuario
        return TestClient(app)
    yield _armar
    for dep in (get_db_propia, api.get_consulta_externa, get_usuario_actual):
        app.dependency_overrides.pop(dep, None)


# ─── Con Ver ────────────────────────────────────────────────────────────────

def test_con_ver_el_get_trae_las_sin_definir_primero(cliente, db):
    db.add(TareaFacturacion(tarea_id=10, unidad_sugerida="hectareas"))
    db.commit()

    r = cliente(contadora("ver")).get(URL)

    assert r.status_code == 200
    assert r.json() == [
        {"tarea_id": 20, "nombre": "TAREA B", "grupo_tarea": None,
         "unidad_sugerida": None, "no_facturable": False, "sin_definir": True},
        {"tarea_id": 30, "nombre": "TAREA C", "grupo_tarea": "GRUPO 2",
         "unidad_sugerida": None, "no_facturable": False, "sin_definir": True},
        {"tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "GRUPO 1",
         "unidad_sugerida": "hectareas", "no_facturable": False, "sin_definir": False},
    ]


def test_con_ver_el_patch_da_403(cliente, db):
    r = cliente(contadora("ver")).patch(
        f"{URL}/10", json={"unidad_sugerida": "plantas", "no_facturable": False})
    assert r.status_code == 403
    assert r.json()["detail"] == "No tenés permiso para esta operación"
    assert db.query(TareaFacturacion).count() == 0


# ─── Con Editar ─────────────────────────────────────────────────────────────

def test_con_editar_el_patch_devuelve_el_item(cliente, db):
    r = cliente(contadora("editar")).patch(
        f"{URL}/10", json={"unidad_sugerida": "plantas", "no_facturable": False})
    assert r.status_code == 200
    assert r.json() == {
        "tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "GRUPO 1",
        "unidad_sugerida": "plantas", "no_facturable": False, "sin_definir": False,
    }
    fila = db.query(TareaFacturacion).filter_by(tarea_id=10).one()
    assert fila.actualizado_por == 1


def test_las_dos_a_la_vez_dan_422(cliente):
    r = cliente(contadora("editar")).patch(
        f"{URL}/10", json={"unidad_sugerida": "plantas", "no_facturable": True})
    assert r.status_code == 422
    assert r.json()["detail"] == "Una tarea tiene Unidad sugerida o es No facturable, no las dos."


def test_una_unidad_desconocida_da_422(cliente):
    r = cliente(contadora("editar")).patch(
        f"{URL}/10", json={"unidad_sugerida": "toneladas", "no_facturable": False})
    assert r.status_code == 422
    assert r.json()["detail"] == "Unidad de facturación desconocida: toneladas."


def test_una_tarea_inactiva_da_404(cliente, db):
    r = cliente(contadora("editar")).patch(
        f"{URL}/99", json={"unidad_sugerida": "plantas", "no_facturable": False})
    assert r.status_code == 404
    assert r.json()["detail"] == "La tarea no está entre las activas del sistema de campo."
    assert db.query(TareaFacturacion).count() == 0


def test_volver_a_sin_definir_da_200_con_sin_definir(cliente, db):
    db.add(TareaFacturacion(tarea_id=10, no_facturable=True))
    db.commit()

    r = cliente(contadora("editar")).patch(
        f"{URL}/10", json={"unidad_sugerida": None, "no_facturable": False})

    assert r.status_code == 200
    assert r.json()["sin_definir"] is True
    assert db.query(TareaFacturacion).count() == 0


@pytest.mark.parametrize("cuerpo", [
    {"no_facturable": False},
    {"unidad_sugerida": "plantas"},
])
def test_un_cuerpo_al_que_le_falta_un_campo_da_422(cliente, db, cuerpo):
    r = cliente(contadora("editar")).patch(f"{URL}/10", json=cuerpo)
    assert r.status_code == 422
    # El 422 de FastAPI: una lista con `msg`, que el front lee con mensajeDeError.
    assert isinstance(r.json()["detail"], list)
    assert "msg" in r.json()["detail"][0]
    assert db.query(TareaFacturacion).count() == 0


# ─── Sin la pantalla ────────────────────────────────────────────────────────

def test_el_preliquidador_no_ve_las_tareas(cliente):
    r = cliente(preliquidador()).get(URL)
    assert r.status_code == 403


# ─── El campo caído ─────────────────────────────────────────────────────────

def test_con_el_campo_caido_el_get_da_503(cliente):
    r = cliente(contadora("editar"), campo=CampoCaido()).get(URL)
    assert r.status_code == 503
    assert r.json()["detail"] == CAIDO


def test_con_el_campo_caido_el_patch_da_503(cliente, db):
    r = cliente(contadora("editar"), campo=CampoCaido()).patch(
        f"{URL}/10", json={"unidad_sugerida": "plantas", "no_facturable": False})
    assert r.status_code == 503
    assert r.json()["detail"] == CAIDO
    assert db.query(TareaFacturacion).count() == 0
