"""Mensualizados por CUIL desde el .env del backend (PR4, pasos 4.1 y 4.2).

La config del módulo, la propiedad `mensualizado` de la línea y su paso por
`LineaResponse` y por `GET /api/preliquidacion/{id}/lineas`.

Los CUIL de estos tests son ficticios: el repo es público y la lista real
vive sólo en el .env del servidor.
"""
import logging
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
from app.modulos.preliquidacion.schemas import LineaResponse
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService
from app.modulos.preliquidacion import config as modulo_config
from app.modulos.preliquidacion.config import (
    ConfigPreliquidacion,
    cuils_mensualizados,
    es_mensualizado,
)

CUIL_MENSUALIZADO = "20111111119"


def _con_lista(monkeypatch, valor: str) -> None:
    # `_env_file=None` para que el test no dependa del .env de la máquina.
    monkeypatch.setattr(
        modulo_config,
        "config",
        ConfigPreliquidacion(_env_file=None, empleados_mensualizados_cuil=valor),
    )


def test_normaliza_e_ignora_vacios(monkeypatch):
    _con_lista(monkeypatch, "20-11111111-9, 27222222223 ,,")
    assert cuils_mensualizados() == {"20111111119", "27222222223"}


def test_vacio_es_nadie(monkeypatch):
    _con_lista(monkeypatch, "")
    assert cuils_mensualizados() == set()
    assert es_mensualizado("20111111119") is False


def test_entrada_invalida_se_ignora_con_aviso(monkeypatch, caplog):
    _con_lista(monkeypatch, "pepe, 20111111119, 12345678")
    # El parseo se cachea por texto para no repetir el aviso en cada línea;
    # se limpia para que el aviso salga en este test aunque otro haya
    # parseado el mismo texto antes.
    modulo_config._parsear.cache_clear()
    with caplog.at_level(logging.WARNING, logger="app.modulos.preliquidacion.config"):
        assert cuils_mensualizados() == {"20111111119"}
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 2
    assert "EMPLEADOS_MENSUALIZADOS_CUIL" in avisos[0].getMessage()
    # Con la misma config, el aviso no se repite en cada llamada.
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="app.modulos.preliquidacion.config"):
        cuils_mensualizados()
        es_mensualizado("20111111119")
    assert caplog.records == []


def test_lee_la_variable_de_entorno(monkeypatch):
    # El nombre de la variable es el contrato con el .env del VPS.
    monkeypatch.setenv("EMPLEADOS_MENSUALIZADOS_CUIL", "20111111119")
    assert ConfigPreliquidacion(_env_file=None).empleados_mensualizados_cuil == "20111111119"


def test_sin_variable_el_default_es_vacio(monkeypatch):
    monkeypatch.delenv("EMPLEADOS_MENSUALIZADOS_CUIL", raising=False)
    assert ConfigPreliquidacion(_env_file=None).empleados_mensualizados_cuil == ""


@pytest.mark.parametrize(
    "cuit, esperado",
    [
        ("20111111119", True),
        (" 20-11111111-9 ", True),
        ("27222222223", False),
        (None, False),
        ("", False),
        ("12345678", False),
    ],
)
def test_es_mensualizado(monkeypatch, cuit, esperado):
    _con_lista(monkeypatch, "20111111119")
    assert es_mensualizado(cuit) is esperado


def test_se_calcula_en_cada_llamada(monkeypatch):
    # Los tests del paso 4.2 cambian el atributo de la instancia con
    # monkeypatch; si el set quedara congelado al importar, no lo verían.
    _con_lista(monkeypatch, "")
    assert cuils_mensualizados() == set()
    monkeypatch.setattr(modulo_config.config, "empleados_mensualizados_cuil", "20111111119")
    assert cuils_mensualizados() == {"20111111119"}


# ─── Paso 4.2: la línea sabe si es de un mensualizado ────────────────────────

def _linea_suelta(**kw) -> PreliquidacionLinea:
    # Sin base: la propiedad y el schema sólo leen atributos del objeto.
    datos = dict(
        id=1, preliquidacion_id=1, es_duplicado=False, es_posible_duplicado=False,
        alerta_legajo=False,
        alerta_empresa=False, linea_incompleta=False,
    )
    datos.update(kw)
    return PreliquidacionLinea(**datos)


def test_propiedad_mensualizado(monkeypatch):
    _con_lista(monkeypatch, CUIL_MENSUALIZADO)
    assert _linea_suelta(cuit=CUIL_MENSUALIZADO).mensualizado is True
    assert _linea_suelta(cuit="20333333339").mensualizado is False
    assert _linea_suelta(cuit=None).mensualizado is False


def test_propiedad_con_la_config_vacia_es_false(monkeypatch):
    _con_lista(monkeypatch, "")
    assert _linea_suelta(cuit=CUIL_MENSUALIZADO).mensualizado is False


def test_linea_response_trae_mensualizado(monkeypatch):
    _con_lista(monkeypatch, CUIL_MENSUALIZADO)
    linea = _linea_suelta(cuit=CUIL_MENSUALIZADO)
    assert LineaResponse.model_validate(linea, from_attributes=True).mensualizado is True
    _con_lista(monkeypatch, "")
    assert LineaResponse.model_validate(linea, from_attributes=True).mensualizado is False


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


def test_endpoint_lineas_trae_mensualizado(monkeypatch, db, cliente):
    monkeypatch.setattr(modulo_config.config, "empleados_mensualizados_cuil", CUIL_MENSUALIZADO)
    p = Preliquidacion(quincena=date(2026, 5, 1), creado_por=1)
    db.add(p)
    db.commit()
    for cuit, nombre in [(CUIL_MENSUALIZADO, "EMPLEADO, MENSUALIZADO"),
                         ("20333333339", "OTRO, EMPLEADO"),
                         (None, "SIN, CUIL")]:
        db.add(PreliquidacionLinea(
            preliquidacion_id=p.id, cuit=cuit, nombre_empleado=nombre,
            hsjornal=Decimal("8"), importe_total=Decimal("0"),
        ))
    db.commit()

    r = cliente.get(f"/api/preliquidacion/{p.id}/lineas")

    assert r.status_code == 200
    por_nombre = {l["nombre_empleado"]: l["mensualizado"] for l in r.json()}
    assert por_nombre == {
        "EMPLEADO, MENSUALIZADO": True,
        "OTRO, EMPLEADO": False,
        "SIN, CUIL": False,
    }


# ─── Paso 4.2: el filtro SQL compartido por Verificación y Gerencial ─────────

def test_filtro_con_la_config_vacia_no_arma_un_not_in_vacio(monkeypatch):
    # `notin_([])` emite un warning de SQLAlchemy y en algunos dialectos
    # compila a `1 != 1`: con nadie mensualizado el filtro es un TRUE liso.
    from app.modulos.preliquidacion.services.preliquidacion_service import filtro_no_mensualizado
    _con_lista(monkeypatch, "")
    assert "NOT IN" not in str(filtro_no_mensualizado()).upper()


def test_filtro_con_mensualizados_deja_pasar_las_lineas_sin_cuit(monkeypatch):
    from app.modulos.preliquidacion.services.preliquidacion_service import filtro_no_mensualizado
    _con_lista(monkeypatch, CUIL_MENSUALIZADO)
    sql = str(filtro_no_mensualizado().compile(compile_kwargs={"literal_binds": True})).upper()
    assert "IS NULL" in sql
    assert "NOT IN" in sql
    assert CUIL_MENSUALIZADO in sql
