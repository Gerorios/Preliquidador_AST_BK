"""La regla de la Unidad sugerida por tarea (plan de la E1, D4 y contrato 2.5).

SQLite en memoria para la tabla propia; las tareas del campo llegan como
listas, igual que las devuelve ConsultaExternaService.obtener_tareas().
Todos los datos son ficticios.
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modulos.facturacion.models import TareaFacturacion
from app.modulos.facturacion.services.unidad_service import (
    DefinicionInvalida,
    TareaNoEncontrada,
    UnidadService,
)

USUARIO = 7
TOLERANCIA = timedelta(seconds=5)


def tarea(tarea_id, nombre, grupo="GRUPO 1"):
    return {"tarea_id": tarea_id, "nombre": nombre, "grupo_tarea": grupo}


# El orden del campo es por nombre.
CAMPO = [
    tarea(10, "TAREA A"),
    tarea(20, "TAREA B"),
    tarea(30, "TAREA C", grupo=None),
    tarea(40, "TAREA D"),
]


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _fila(db, tarea_id):
    db.expire_all()
    return db.query(TareaFacturacion).filter_by(tarea_id=tarea_id).one_or_none()


def _por_id(items):
    return {i["tarea_id"]: i for i in items}


# ─── listar ─────────────────────────────────────────────────────────────────

def test_1_una_tarea_sin_fila_esta_sin_definir(db):
    item = _por_id(UnidadService(db).listar(CAMPO))[10]
    assert item == {
        "tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "GRUPO 1",
        "unidad_sugerida": None, "no_facturable": False, "sin_definir": True,
    }


def test_2_con_una_unidad_agricola_no_esta_sin_definir(db):
    db.add(TareaFacturacion(tarea_id=10, unidad_sugerida="hectareas"))
    db.commit()
    item = _por_id(UnidadService(db).listar(CAMPO))[10]
    assert item["unidad_sugerida"] == "hectareas"
    assert item["no_facturable"] is False
    assert item["sin_definir"] is False


def test_3_con_una_unidad_de_cosecha_no_esta_sin_definir(db):
    # Criterio de la E1: la cosecha cuenta como con unidad. Sacarla del Cruce
    # y de las Alertas es de la E3.
    db.add(TareaFacturacion(tarea_id=10, unidad_sugerida="bins_c"))
    db.commit()
    item = _por_id(UnidadService(db).listar(CAMPO))[10]
    assert item["unidad_sugerida"] == "bins_c"
    assert item["sin_definir"] is False


def test_4_no_facturable_no_esta_sin_definir(db):
    db.add(TareaFacturacion(tarea_id=10, no_facturable=True))
    db.commit()
    item = _por_id(UnidadService(db).listar(CAMPO))[10]
    assert item["unidad_sugerida"] is None
    assert item["no_facturable"] is True
    assert item["sin_definir"] is False


def test_5_las_sin_definir_van_primero_y_cada_grupo_conserva_el_orden_del_campo(db):
    db.add_all([
        TareaFacturacion(tarea_id=10, unidad_sugerida="plantas"),
        TareaFacturacion(tarea_id=30, no_facturable=True),
    ])
    db.commit()
    ids = [i["tarea_id"] for i in UnidadService(db).listar(CAMPO)]
    assert ids == [20, 40, 10, 30]


def test_6_la_fila_de_una_tarea_inactiva_no_aparece_y_no_se_borra(db):
    db.add(TareaFacturacion(tarea_id=99, unidad_sugerida="viajes"))
    db.commit()
    ids = [i["tarea_id"] for i in UnidadService(db).listar(CAMPO)]
    assert 99 not in ids
    assert ids == [10, 20, 30, 40]
    assert _fila(db, 99).unidad_sugerida == "viajes"


# ─── definir ────────────────────────────────────────────────────────────────

def test_7_definir_crea_cambia_y_vuelve_a_sin_definir(db):
    servicio = UnidadService(db)

    item = servicio.definir(CAMPO, 20, "horas_peon", False, USUARIO)
    assert item == {
        "tarea_id": 20, "nombre": "TAREA B", "grupo_tarea": "GRUPO 1",
        "unidad_sugerida": "horas_peon", "no_facturable": False, "sin_definir": False,
    }
    fila = _fila(db, 20)
    assert (fila.unidad_sugerida, fila.no_facturable) == ("horas_peon", False)

    # De una unidad a No facturable: la unidad queda en NULL.
    item = servicio.definir(CAMPO, 20, None, True, USUARIO)
    assert (item["unidad_sugerida"], item["no_facturable"], item["sin_definir"]) == (None, True, False)
    fila = _fila(db, 20)
    assert (fila.unidad_sugerida, fila.no_facturable) == (None, True)
    assert db.query(TareaFacturacion).count() == 1

    # Volver a Sin definir borra la fila.
    item = servicio.definir(CAMPO, 20, None, False, USUARIO)
    assert (item["unidad_sugerida"], item["no_facturable"], item["sin_definir"]) == (None, False, True)
    assert _fila(db, 20) is None


def test_7b_volver_a_sin_definir_una_tarea_sin_fila_no_falla(db):
    item = UnidadService(db).definir(CAMPO, 20, None, False, USUARIO)
    assert item["sin_definir"] is True
    assert db.query(TareaFacturacion).count() == 0


def test_8_las_dos_a_la_vez_es_un_error(db):
    with pytest.raises(DefinicionInvalida) as exc:
        UnidadService(db).definir(CAMPO, 20, "hectareas", True, USUARIO)
    assert str(exc.value) == "Una tarea tiene Unidad sugerida o es No facturable, no las dos."
    assert _fila(db, 20) is None


def test_9_una_unidad_desconocida_es_un_error_que_nombra_el_valor(db):
    with pytest.raises(DefinicionInvalida) as exc:
        UnidadService(db).definir(CAMPO, 20, "toneladas", False, USUARIO)
    assert str(exc.value) == "Unidad de facturación desconocida: toneladas."
    assert _fila(db, 20) is None


def test_10_una_tarea_que_no_esta_activa_no_se_encuentra(db):
    with pytest.raises(TareaNoEncontrada) as exc:
        UnidadService(db).definir(CAMPO, 99, "hectareas", False, USUARIO)
    assert str(exc.value) == "La tarea no está entre las activas del sistema de campo."
    assert _fila(db, 99) is None


def test_11_se_guardan_actualizado_por_y_actualizado_en(db):
    antes = datetime(2026, 1, 1)
    db.add(TareaFacturacion(tarea_id=20, unidad_sugerida="plantas", actualizado_en=antes))
    db.commit()

    UnidadService(db).definir(CAMPO, 20, "tancadas", False, USUARIO)

    fila = _fila(db, 20)
    assert fila.actualizado_por == USUARIO
    assert fila.actualizado_en.tzinfo is None
    ahora = datetime.now(UTC).replace(tzinfo=None)
    assert abs(fila.actualizado_en - ahora) <= TOLERANCIA


# ─── dos personas a la vez: gana la última que guarda (plan, 3.7, R1) ───────
#
# La otra persona escribe entre nuestra lectura y nuestro commit: un hook
# before_flush (una sola vez) le hace escribir y commitear con otra sesión.
# SQLite en archivo y no en memoria, para que sean dos conexiones de verdad.

@pytest.fixture()
def dos_sesiones(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'facturacion.db'}")
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine)
    nuestra, otra = Sesion(), Sesion()
    yield nuestra, otra
    nuestra.close()
    otra.close()
    engine.dispose()


def _antes_de_nuestro_commit(sesion, hacer):
    def hook(session, flush_context, instances):
        hacer()
    event.listen(sesion, "before_flush", hook, once=True)


def test_12_si_otra_la_crea_a_la_vez_gana_la_nuestra(dos_sesiones):
    nuestra, otra = dos_sesiones

    def otra_la_crea():
        otra.add(TareaFacturacion(tarea_id=20, unidad_sugerida="plantas"))
        otra.commit()

    _antes_de_nuestro_commit(nuestra, otra_la_crea)
    item = UnidadService(nuestra).definir(CAMPO, 20, "tancadas", False, USUARIO)

    assert item["unidad_sugerida"] == "tancadas"
    otra.expire_all()
    filas = otra.query(TareaFacturacion).filter_by(tarea_id=20).all()
    assert [(f.unidad_sugerida, f.no_facturable, f.actualizado_por) for f in filas] == [
        ("tancadas", False, USUARIO)]


def test_13_si_otra_la_deja_sin_definir_a_la_vez_gana_la_nuestra(dos_sesiones):
    nuestra, otra = dos_sesiones
    nuestra.add(TareaFacturacion(tarea_id=20, unidad_sugerida="plantas"))
    nuestra.commit()

    def otra_la_borra():
        otra.query(TareaFacturacion).filter_by(tarea_id=20).delete()
        otra.commit()

    _antes_de_nuestro_commit(nuestra, otra_la_borra)
    item = UnidadService(nuestra).definir(CAMPO, 20, None, True, USUARIO)

    assert (item["unidad_sugerida"], item["no_facturable"]) == (None, True)
    otra.expire_all()
    filas = otra.query(TareaFacturacion).filter_by(tarea_id=20).all()
    assert [(f.unidad_sugerida, f.no_facturable) for f in filas] == [(None, True)]

