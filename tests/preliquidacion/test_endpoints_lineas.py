"""Tests de caracterización de dos endpoints sin cobertura (PR3, paso 3.7):

- POST /api/preliquidacion/lineas/legajos-por-cuil (picker de reasignación
  masiva de empresa).
- GET /api/precios/conceptos/buscar (combo de códigos del PanelLinea).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
datos de personas son ficticios.

Roles: el router de preliquidación exige `requiere_operativo` (admin u
operador del módulo); el de precios sólo exige sesión (`get_usuario_actual`)
y este GET no agrega nada, así que lo ve cualquier usuario logueado. Se usa
admin para los dos.
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
from app.core.sueldos_service import SueldosService
from app.main import app
from app.modulos.preliquidacion.api import preliquidacion as api
from app.modulos.preliquidacion.models import (
    ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea, TipoConcepto,
)
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
URL_LEGAJOS = "/api/preliquidacion/lineas/legajos-por-cuil"
URL_BUSCAR = "/api/precios/conceptos/buscar"


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
    # Sin `with`: no corre el lifespan (que verifica las conexiones reales).
    yield TestClient(app)
    app.dependency_overrides.clear()


def _sueldos_con(por_cuil: dict) -> SueldosService:
    """SueldosService con el cache ya poblado a mano (sin BD externa real),
    igual que test_reasignacion_empresa.py."""
    s = SueldosService.__new__(SueldosService)
    s._cache_cargado = True
    s._por_legajo = {}
    s._por_legajo_empresa = {}
    s._por_cuil = por_cuil
    return s


def _con_service(db, sueldos):
    """Override de api.get_service. PreliquidacionService no recibe `sueldos`
    en el constructor (recibe la sesión `db_sueldos` y arma el SueldosService
    adentro): se construye sin esa sesión y se inyecta el atributo después."""
    def _factory():
        svc = PreliquidacionService(db)
        svc.sueldos = sueldos
        return svc
    app.dependency_overrides[api.get_service] = _factory


def _preliq(db, quincena=Q1):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, cuit, nombre_empleado):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit=cuit, nombre_empleado=nombre_empleado, legajo_campo="0000",
        empresa_asignada="LA ASTURIANA", legajo_asignado="0000",
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"),
        hsmaquina=Decimal("0"), importe_total=Decimal("0"),
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, codigo, tipo=TipoConcepto.OTRO, quincena=Q1, tarea="TAREA X",
              precio=Decimal("100"), categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, codigo=codigo,
        precio=precio, tipo=tipo, categoria=categoria,
    )
    db.add(c)
    db.commit()
    return c


# ─── POST /lineas/legajos-por-cuil ────────────────────────────────────────────

def test_legajos_por_cuil_sin_linea_ids_da_400(cliente, db):
    _con_service(db, _sueldos_con({}))
    r = cliente.post(URL_LEGAJOS, json={"linea_ids": []})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Se requieren linea_ids"


def test_legajos_por_cuil_agrupa_por_cuil_y_separa_sin_cuil(cliente, db):
    preliq = _preliq(db)
    l1 = _linea(db, preliq, "20111111119", "PEREZ JUAN")
    l2 = _linea(db, preliq, "20111111119", "PEREZ JUAN")  # misma persona, otro día
    l3 = _linea(db, preliq, "27222222223", "GOMEZ ANA")
    l4 = _linea(db, preliq, "", "SIN CUIL")
    _con_service(db, _sueldos_con({
        "20111111119": [
            {"empresa": "LA ASTURIANA", "legajo": "111", "apellido_nombre": "PEREZ JUAN"},
            {"empresa": "PAMPLONA", "legajo": "999", "apellido_nombre": "PEREZ JUAN"},
        ],
        "27222222223": [{"empresa": "LA ASTURIANA", "legajo": "222"}],
    }))

    r = cliente.post(URL_LEGAJOS, json={"linea_ids": [l1.id, l2.id, l3.id, l4.id]})

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"grupos", "sin_cuil"}
    assert body["sin_cuil"] == [l4.id]
    grupos = {g["cuil"]: g for g in body["grupos"]}
    assert set(grupos) == {"20111111119", "27222222223"}
    perez = grupos["20111111119"]
    assert perez["nombre_empleado"] == "PEREZ JUAN"
    assert sorted(perez["linea_ids"]) == sorted([l1.id, l2.id])
    # Sólo el par (empresa, legajo): los demás campos del maestro no salen.
    assert perez["legajos_disponibles"] == [
        {"empresa": "LA ASTURIANA", "legajo": "111"},
        {"empresa": "PAMPLONA", "legajo": "999"},
    ]
    assert grupos["27222222223"]["linea_ids"] == [l3.id]


def test_legajos_por_cuil_cuil_sin_registros_en_el_maestro_da_lista_vacia(cliente, db):
    preliq = _preliq(db)
    l1 = _linea(db, preliq, "20333333334", "LOPEZ LUIS")
    _con_service(db, _sueldos_con({}))

    r = cliente.post(URL_LEGAJOS, json={"linea_ids": [l1.id]})

    assert r.status_code == 200, r.text
    assert r.json() == {
        "grupos": [{
            "cuil": "20333333334", "nombre_empleado": "LOPEZ LUIS",
            "linea_ids": [l1.id], "legajos_disponibles": [],
        }],
        "sin_cuil": [],
    }


def test_legajos_por_cuil_ids_inexistentes_dan_200_vacio(cliente, db):
    # El endpoint no valida existencia: ids que no están se ignoran.
    _con_service(db, _sueldos_con({}))
    r = cliente.post(URL_LEGAJOS, json={"linea_ids": [9999]})
    assert r.status_code == 200, r.text
    assert r.json() == {"grupos": [], "sin_cuil": []}


def test_legajos_por_cuil_sin_servicio_de_sueldos_da_400(cliente, db):
    preliq = _preliq(db)
    l1 = _linea(db, preliq, "20111111119", "PEREZ JUAN")
    _con_service(db, None)

    r = cliente.post(URL_LEGAJOS, json={"linea_ids": [l1.id]})

    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Servicio de sueldos no disponible"


# ─── GET /{preliq_id}/lineas ──────────────────────────────────────────────────

def test_listar_lineas_expone_es_posible_duplicado(cliente, db):
    preliq = _preliq(db)
    marcada = _linea(db, preliq, "20111111119", "PEREZ JUAN")
    comun = _linea(db, preliq, "27222222223", "GOMEZ ANA")
    marcada.es_posible_duplicado = True
    db.commit()
    _con_service(db, _sueldos_con({}))

    r = cliente.get(f"/api/preliquidacion/{preliq.id}/lineas")

    assert r.status_code == 200, r.text
    por_id = {l["id"]: l for l in r.json()}
    assert por_id[marcada.id]["es_posible_duplicado"] is True
    assert por_id[comun.id]["es_posible_duplicado"] is False


# ─── GET /api/precios/conceptos/buscar ────────────────────────────────────────

def test_buscar_sin_q_devuelve_codigos_distintos_ordenados(cliente, db):
    _concepto(db, 500, TipoConcepto.JORNAL)
    _concepto(db, 461, TipoConcepto.REMUNERATIVO)
    _concepto(db, 461, TipoConcepto.REMUNERATIVO, tarea="TAREA Y")  # mismo código
    _concepto(db, 461, TipoConcepto.REMUNERATIVO, quincena=Q2)       # otra quincena
    _concepto(db, 120, TipoConcepto.NO_REMUNERATIVO)
    _concepto(db, None, TipoConcepto.OTRO, tarea="SIN CODIGO")       # no entra

    r = cliente.get(URL_BUSCAR)

    assert r.status_code == 200, r.text
    assert r.json() == [
        {"codigo": 120, "tipo": "NO_REMUNERATIVO"},
        {"codigo": 461, "tipo": "REMUNERATIVO"},
        {"codigo": 500, "tipo": "JORNAL"},
    ]


def test_buscar_q_numerico_filtra_por_codigo_exacto(cliente, db):
    _concepto(db, 461, TipoConcepto.REMUNERATIVO)
    _concepto(db, 46, TipoConcepto.OTRO)
    _concepto(db, 4610, TipoConcepto.OTRO)

    r = cliente.get(URL_BUSCAR, params={"q": "461"})
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 461, "tipo": "REMUNERATIVO"}]

    # Igualdad, no prefijo: "46" no trae 461 ni 4610. Los espacios se recortan.
    r = cliente.get(URL_BUSCAR, params={"q": " 46 "})
    assert r.json() == [{"codigo": 46, "tipo": "OTRO"}]


def test_buscar_q_texto_filtra_por_tipo_sin_distinguir_mayusculas(cliente, db):
    _concepto(db, 461, TipoConcepto.REMUNERATIVO)
    _concepto(db, 120, TipoConcepto.NO_REMUNERATIVO)
    _concepto(db, 500, TipoConcepto.JORNAL)

    r = cliente.get(URL_BUSCAR, params={"q": "remu"})
    assert r.status_code == 200, r.text
    # "remu" también matchea NO_REMUNERATIVO (es un ilike %remu%).
    assert r.json() == [
        {"codigo": 120, "tipo": "NO_REMUNERATIVO"},
        {"codigo": 461, "tipo": "REMUNERATIVO"},
    ]

    r = cliente.get(URL_BUSCAR, params={"q": "nada"})
    assert r.json() == []


def test_buscar_quincena_acota(cliente, db):
    _concepto(db, 461, TipoConcepto.REMUNERATIVO, quincena=Q1)
    _concepto(db, 500, TipoConcepto.JORNAL, quincena=Q2)

    r = cliente.get(URL_BUSCAR, params={"quincena": Q2.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 500, "tipo": "JORNAL"}]

    r = cliente.get(URL_BUSCAR, params={"quincena": Q2.isoformat(), "q": "461"})
    assert r.json() == []


def test_buscar_devuelve_como_maximo_200(cliente, db):
    for codigo in range(1, 206):
        db.add(ConceptoLiquidacion(
            quincena=Q1, tarea_nombre="TAREA X", codigo=codigo,
            precio=Decimal("1"), tipo=TipoConcepto.OTRO,
        ))
    db.commit()

    r = cliente.get(URL_BUSCAR)

    assert r.status_code == 200, r.text
    codigos = [f["codigo"] for f in r.json()]
    assert len(codigos) == 200
    assert codigos == list(range(1, 201))


def test_buscar_no_pierde_codigos_con_mas_de_200_filas_del_mismo_codigo(cliente, db):
    # El tope de 200 se aplica después de agrupar por código: 250 filas del
    # mismo código no pueden tapar a los códigos que vienen después.
    for i in range(250):
        db.add(ConceptoLiquidacion(
            quincena=Q1, tarea_nombre=f"TAREA {i}", codigo=1,
            precio=Decimal("1"), tipo=TipoConcepto.OTRO,
        ))
    db.commit()
    _concepto(db, 2, TipoConcepto.JORNAL)

    esperado = [
        {"codigo": 1, "tipo": "OTRO"},
        {"codigo": 2, "tipo": "JORNAL"},
    ]
    r = cliente.get(URL_BUSCAR, params={"quincena": Q1.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json() == esperado

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == esperado


def test_buscar_excluye_codigos_sin_ninguna_fila_con_precio(cliente, db):
    _concepto(db, 700, TipoConcepto.OTRO, precio=None)
    _concepto(db, 701, TipoConcepto.OTRO, precio=None)
    _concepto(db, 701, TipoConcepto.OTRO, tarea="TAREA Y")  # con precio

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 701, "tipo": "OTRO"}]

    r = cliente.get(URL_BUSCAR, params={"q": "700"})
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_buscar_tipo_mas_frecuente_entre_filas_con_precio(cliente, db):
    # Las filas sin precio no cuentan: OTRO tiene más filas pero ninguna con
    # precio, así que gana JORNAL (2) sobre REMUNERATIVO (1).
    _concepto(db, 800, TipoConcepto.REMUNERATIVO, tarea="TAREA R")
    _concepto(db, 800, TipoConcepto.JORNAL, tarea="TAREA J1")
    _concepto(db, 800, TipoConcepto.JORNAL, tarea="TAREA J2")
    for i in range(3):
        _concepto(db, 800, TipoConcepto.OTRO, tarea=f"TAREA O{i}", precio=None)

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 800, "tipo": "JORNAL"}]


def test_buscar_empate_de_tipos_desempata_por_nombre_de_tipo(cliente, db):
    # Empate 1 a 1: gana el nombre de tipo menor (JORNAL < REMUNERATIVO),
    # aunque REMUNERATIVO se haya cargado primero.
    _concepto(db, 900, TipoConcepto.REMUNERATIVO, tarea="TAREA R")
    _concepto(db, 900, TipoConcepto.JORNAL, tarea="TAREA J")

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 900, "tipo": "JORNAL"}]


def test_buscar_excluye_codigos_que_solo_tienen_reglas_con_categoria(cliente, db):
    # Las reglas por categoría no se ofrecen como Concepto extra (ADR-0015):
    # un código que sólo las tiene no aparece, aunque tengan precio.
    _concepto(db, 950, TipoConcepto.JORNAL, tarea="TAREA C1", categoria=3)
    _concepto(db, 950, TipoConcepto.JORNAL, tarea="TAREA C2", categoria=5)
    _concepto(db, 951, TipoConcepto.OTRO)  # sin categoría, con precio

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 951, "tipo": "OTRO"}]

    r = cliente.get(URL_BUSCAR, params={"q": "950"})
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_buscar_tipo_sale_solo_de_las_reglas_sin_categoria(cliente, db):
    # Si contaran las reglas con categoría, JORNAL (2) le ganaría a
    # REMUNERATIVO (1); como no cuentan, el tipo es REMUNERATIVO.
    _concepto(db, 960, TipoConcepto.JORNAL, tarea="TAREA C1", categoria=3)
    _concepto(db, 960, TipoConcepto.JORNAL, tarea="TAREA C2", categoria=5)
    _concepto(db, 960, TipoConcepto.REMUNERATIVO, tarea="TAREA S")

    r = cliente.get(URL_BUSCAR)
    assert r.status_code == 200, r.text
    assert r.json() == [{"codigo": 960, "tipo": "REMUNERATIVO"}]
