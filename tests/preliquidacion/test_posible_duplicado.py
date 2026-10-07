"""Posible duplicado: línea igual a otra en todo salvo en las horas (jornal o
máquina), con la misma cantidad pagada (unidades o tancadas, mayor a 0). Una
línea duplicada no es además posible duplicado. Datos inventados."""
from datetime import date

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import PreliquidacionLinea, Usuario
from app.modulos.preliquidacion.services.motor_reglas import MotorReglas
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService


def _motor():
    # La detección no toca la DB; alcanza con db=None.
    return MotorReglas(None)


def _fila(**kw):
    base = {
        "planilla": "P1", "fecha_tarea": date(2026, 5, 3), "legajo": "100",
        "nombre_empleado": "JUAN PEREZ", "nombre_tarea": "PULVERIZACION",
        "nombre_cliente": "CLIENTE A", "nombre_finca": "FINCA 1",
        "nombre_tractor": "TRACTOR 1", "implemento": "",
        "hsjornal": 8, "hsmaquina": 4, "tancadas": None, "unidades": 500,
        "cantidad": None, "cuit": "20-11111111-9",
        "nombre_supervisor": "", "nombre_capataz": "",
    }
    base.update(kw)
    return base


# ─── Motor: detectar_posibles_duplicados ─────────────────────────────────────

def test_mismas_unidades_distinta_hs_maquina_son_posibles():
    f1 = _fila(unidades=500, hsmaquina=4)
    f2 = _fila(unidades=500, hsmaquina=5)
    motor = _motor()
    assert motor.detectar_posibles_duplicados([f1, f2]) == {0, 1}
    assert motor.detectar_duplicados([f1, f2]) == set()


def test_mismas_tancadas_distinta_hs_jornal_son_posibles():
    f1 = _fila(unidades=None, tancadas=12, hsmaquina=None, hsjornal=6)
    f2 = _fila(unidades=None, tancadas=12, hsmaquina=None, hsjornal=8)
    motor = _motor()
    assert motor.detectar_posibles_duplicados([f1, f2]) == {0, 1}
    assert motor.detectar_duplicados([f1, f2]) == set()


@pytest.mark.parametrize("sin_cantidad", [None, 0, "0.00"])
def test_sin_cantidad_no_es_posible(sin_cantidad):
    # Tareas por hora: misma cantidad nula o cero con horas distintas es
    # trabajo real, no una duda.
    f1 = _fila(unidades=sin_cantidad, tancadas=None, hsjornal=4)
    f2 = _fila(unidades=sin_cantidad, tancadas=None, hsjornal=8)
    assert _motor().detectar_posibles_duplicados([f1, f2]) == set()


def test_cantidad_distinta_no_es_posible():
    f1 = _fila(unidades=500, hsmaquina=4)
    f2 = _fila(unidades=501, hsmaquina=5)
    assert _motor().detectar_posibles_duplicados([f1, f2]) == set()


@pytest.mark.parametrize("campo, otro_valor", [
    ("fecha_tarea", date(2026, 5, 4)),
    ("legajo", "200"),
    ("nombre_finca", "FINCA 2"),
    ("nombre_tractor", "TRACTOR 2"),
])
def test_otra_fecha_persona_o_finca_no_es_posible(campo, otro_valor):
    f1 = _fila(hsmaquina=4)
    f2 = _fila(hsmaquina=5, **{campo: otro_valor})
    assert _motor().detectar_posibles_duplicados([f1, f2]) == set()


def test_duplicado_no_es_ademas_posible():
    a = _fila(hsmaquina=4)
    b = _fila(hsmaquina=4)
    c = _fila(hsmaquina=5)
    motor = _motor()
    dup = motor.detectar_duplicados([a, b, c])
    assert dup == {0, 1}
    assert motor.detectar_posibles_duplicados([a, b, c], dup) == {2}


def test_grupo_de_solo_identicas_no_genera_posibles():
    a, b, c = _fila(), _fila(), _fila()
    motor = _motor()
    dup = motor.detectar_duplicados([a, b, c])
    assert motor.detectar_posibles_duplicados([a, b, c], dup) == set()
    assert motor.detectar_posibles_duplicados([a, b, c]) == set()


def test_dos_pares_identicos_entre_si_no_generan_posibles():
    a, b = _fila(hsmaquina=4), _fila(hsmaquina=4)
    c, d = _fila(hsmaquina=5), _fila(hsmaquina=5)
    motor = _motor()
    dup = motor.detectar_duplicados([a, b, c, d])
    assert dup == {0, 1, 2, 3}
    assert motor.detectar_posibles_duplicados([a, b, c, d], dup) == set()


def test_normaliza_como_detectar_duplicados():
    # '12.985' y '12.99' son el mismo valor guardado; nombres con espacios y
    # minúsculas cuentan como iguales, igual que en detectar_duplicados.
    f1 = _fila(unidades="12.985", nombre_finca=" finca 1 ", planilla="p1",
               hsmaquina=4)
    f2 = _fila(unidades="12.99", nombre_finca="FINCA 1", planilla="P1",
               hsmaquina=5)
    assert _motor().detectar_posibles_duplicados([f1, f2]) == {0, 1}


# ─── Servicio: ciclo generar / actualizar (SQLite) ───────────────────────────
# Fixture, FakeExterna y _svc copiados de test_actualizar_quincena.py; las filas
# del campo son las de _fila (unidades 500, hsmaquina por parámetro).

Q = date(2026, 5, 1)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Usuario(id=1, nombre="TEST", email="t@t.com", password="x"))
    session.commit()
    yield session
    session.close()


class FakeExterna:
    """Reemplaza ConsultaExternaService: devuelve las filas que le fijemos."""

    def __init__(self, filas=None):
        self.filas = filas or []

    def obtener_tareas_quincena(self, quincena):
        return list(self.filas)

    def obtener_tareas(self):
        return []


def _svc(db, filas):
    svc = PreliquidacionService(db)
    svc.externa = FakeExterna(filas)
    return svc


def _lineas(db):
    return db.query(PreliquidacionLinea).order_by(PreliquidacionLinea.id).all()


def _marcas(db):
    return [(bool(l.es_duplicado), bool(l.es_posible_duplicado)) for l in _lineas(db)]


def test_generar_marca_posible_duplicado_en_el_par(db):
    svc = _svc(db, [_fila(hsmaquina=4), _fila(hsmaquina=5)])
    svc.generar(Q, usuario_id=1)

    assert _marcas(db) == [(False, True), (False, True)]


def test_generar_no_marca_posible_a_la_duplicada(db):
    a, b, c = _fila(hsmaquina=4), _fila(hsmaquina=4), _fila(hsmaquina=5)
    svc = _svc(db, [a, b, c])
    svc.generar(Q, usuario_id=1)

    assert _marcas(db) == [(True, False), (True, False), (False, True)]


def test_actualizar_prende_posible_al_llegar_la_segunda_linea(db):
    """es_posible_duplicado es derivado, como es_duplicado: la compañera que
    llega en una actualización tiene que dejar marcadas a las dos líneas."""
    f1 = _fila(hsmaquina=4)
    svc = _svc(db, [f1])
    svc.generar(Q, usuario_id=1)
    assert _marcas(db) == [(False, False)]

    svc.externa.filas = [f1, _fila(hsmaquina=5)]
    r = svc.generar(Q, usuario_id=1)

    assert r["insertadas"] == 1
    assert _marcas(db) == [(False, True), (False, True)]


def test_actualizar_apaga_posible_al_borrar_la_companera(db):
    f1, f2 = _fila(hsmaquina=4), _fila(hsmaquina=5)
    svc = _svc(db, [f1, f2])
    svc.generar(Q, usuario_id=1)
    assert _marcas(db) == [(False, True), (False, True)]

    svc.externa.filas = [f1]
    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 1
    assert _marcas(db) == [(False, False)]


def test_sin_cambios_no_toca_la_marca(db):
    """Sin altas ni bajas no se recalcula: la marca queda como estaba (por
    ejemplo, como la dejó el backfill de ws18)."""
    f1, f2 = _fila(hsmaquina=4), _fila(hsmaquina=5)
    svc = _svc(db, [f1, f2])
    svc.generar(Q, usuario_id=1)
    primera = _lineas(db)[0]
    primera.es_posible_duplicado = False
    db.commit()

    r = svc.generar(Q, usuario_id=1)

    assert (r["insertadas"], r["eliminadas"], r["sin_cambios"]) == (0, 0, 2)
    assert _marcas(db) == [(False, False), (False, True)]
