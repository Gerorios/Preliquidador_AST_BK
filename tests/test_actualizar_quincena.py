from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    ConceptoAdicional, UnidadBaseConcepto, TipoConcepto,
)
from app.services.preliquidacion_service import PreliquidacionService

Q = date(2026, 5, 1)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
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


def _fila(legajo="100", nombre="JUAN PEREZ", tarea="COSECHA LIMON",
          cliente="CLIENTE A", finca="FINCA 1", fecha=date(2026, 5, 3),
          hsjornal=8, planilla="P1", cuit="20-11111111-9"):
    return {
        "planilla": planilla, "fecha_tarea": fecha, "legajo": legajo,
        "nombre_empleado": nombre, "nombre_tarea": tarea,
        "nombre_cliente": cliente, "nombre_finca": finca,
        "nombre_tractor": "", "implemento": "",
        "hsjornal": hsjornal, "hsmaquina": None, "tancadas": None,
        "unidades": None, "cantidad": None,
        "cuit": cuit, "nombre_supervisor": "", "nombre_capataz": "",
    }


def _svc(db, filas):
    svc = PreliquidacionService(db)
    svc.externa = FakeExterna(filas)
    return svc


def _concepto(db, tarea="COSECHA LIMON", codigo=50, precio=Decimal("100")):
    c = ConceptoLiquidacion(
        quincena=Q, tarea_nombre=tarea, codigo=codigo, precio=precio,
        unidad_base=UnidadBaseConcepto.HSJORNAL, tipo=TipoConcepto.OTRO,
    )
    db.add(c)
    db.commit()
    return c


def _lineas(db):
    return db.query(PreliquidacionLinea).order_by(PreliquidacionLinea.id).all()


# ─── Multiplicidad: el diff debe comparar CANTIDADES, no solo claves ─────────

def test_borrar_una_de_dos_cargas_identicas_elimina_una_linea(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    assert len(_lineas(db)) == 2

    svc.externa.filas = [fila]
    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 1
    assert len(_lineas(db)) == 1


def test_agregar_segunda_carga_identica_inserta_otra_linea(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila])
    svc.generar(Q, usuario_id=1)
    assert len(_lineas(db)) == 1

    svc.externa.filas = [fila, dict(fila)]
    r = svc.generar(Q, usuario_id=1)

    assert r["insertadas"] == 1
    lineas = _lineas(db)
    assert len(lineas) == 2
    # ambas pagan: 8 hs × $100
    assert [l.importe_total for l in lineas] == [Decimal("800.00")] * 2


def test_al_borrar_exceso_sobrevive_la_linea_con_concepto_manual(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    l1, l2 = _lineas(db)

    manual = ConceptoAdicional(
        linea_id=l1.id, descripcion="BONO A MANO", importe=Decimal("500"),
        ingresado_por=1,
    )
    db.add(manual)
    db.commit()

    svc.externa.filas = [fila]
    svc.generar(Q, usuario_id=1)

    lineas = _lineas(db)
    assert len(lineas) == 1
    assert lineas[0].id == l1.id  # sobrevive la que tiene el concepto manual
    descripciones = [c.descripcion for c in lineas[0].conceptos]
    assert "BONO A MANO" in descripciones


def test_carga_borrada_del_campo_desaparece(db):
    _concepto(db)
    fila_a = _fila(legajo="100")
    fila_b = _fila(legajo="200", nombre="MARIA GOMEZ", cuit="27-22222222-9")
    svc = _svc(db, [fila_a, fila_b])
    svc.generar(Q, usuario_id=1)
    assert len(_lineas(db)) == 2

    svc.externa.filas = [fila_a]
    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 1
    lineas = _lineas(db)
    assert len(lineas) == 1
    assert lineas[0].legajo_campo == "100"


def test_sin_cambios_no_toca_nada(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    ids_antes = [l.id for l in _lineas(db)]

    r = svc.generar(Q, usuario_id=1)

    assert r["insertadas"] == 0
    assert r["eliminadas"] == 0
    assert [l.id for l in _lineas(db)] == ids_antes
