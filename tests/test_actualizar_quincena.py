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
    # FKs reales: sin esto SQLite no valida claves foráneas y el orden de los
    # DELETE de actualizar_quincena quedaría sin cobertura.
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Con FKs activas, preliquidacion.creado_por y los ids de usuario de los
    # conceptos manuales necesitan un usuario real.
    from app.models.models import Usuario
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


def test_cargas_que_difieren_en_supervisor_son_claves_distintas(db):
    """El supervisor determina el pago (ADR-0011): dos cargas iguales salvo el
    supervisor NO son intercambiables — al borrar una, debe morir la correcta."""
    _concepto(db)  # común $100/hs
    sup = ConceptoLiquidacion(
        quincena=Q, tarea_nombre="COSECHA LIMON", supervisor_nombre="SUP X",
        codigo=60, precio=Decimal("999"), unidad_base=UnidadBaseConcepto.HSJORNAL,
        tipo=TipoConcepto.OTRO, reemplaza_comun=True,
    )
    db.add(sup)
    db.commit()

    fila_comun = _fila()
    fila_sup = dict(_fila(), nombre_supervisor="SUP X")
    svc = _svc(db, [fila_comun, fila_sup])
    svc.generar(Q, usuario_id=1)
    assert sorted(l.importe_total for l in _lineas(db)) == [
        Decimal("800.00"), Decimal("7992.00")  # 8×100 y 8×999
    ]

    # El campo borra la carga SIN supervisor: debe sobrevivir la de SUP X.
    svc.externa.filas = [fila_sup]
    svc.generar(Q, usuario_id=1)

    lineas = _lineas(db)
    assert len(lineas) == 1
    assert lineas[0].importe_total == Decimal("7992.00")
    assert (lineas[0].nombre_supervisor or "") == "SUP X"


def test_quincena_vaciada_borra_todas_las_lineas(db):
    _concepto(db)
    svc = _svc(db, [_fila(), _fila(legajo="200", cuit="27-2")])
    svc.generar(Q, usuario_id=1)
    assert len(_lineas(db)) == 2

    svc.externa.filas = []
    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 2
    assert _lineas(db) == []
    assert db.query(ConceptoAdicional).count() == 0


def test_ajuste_manual_tambien_protege_del_borrado(db):
    from app.models.models import AjusteManual
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    l1, l2 = _lineas(db)

    db.add(AjusteManual(linea_id=l1.id, usuario_id=1,
                        campo_modificado="empresa_asignada",
                        valor_anterior="A", valor_nuevo="B"))
    db.commit()

    svc.externa.filas = [fila]
    svc.generar(Q, usuario_id=1)

    lineas = _lineas(db)
    assert len(lineas) == 1
    assert lineas[0].id == l1.id  # sobrevive la auditada


def test_exceso_mayor_que_sacrificables_borra_tambien_protegidas(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    l1, l2 = _lineas(db)
    for l in (l1, l2):
        db.add(ConceptoAdicional(linea_id=l.id, descripcion="BONO",
                                 importe=Decimal("1"), ingresado_por=1))
    db.commit()

    svc.externa.filas = []  # exceso 2, sacrificables 0
    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 2
    assert _lineas(db) == []


def test_flag_duplicado_se_prende_al_agregar_copia_incremental(db):
    """es_duplicado es derivado: agregar la segunda copia por actualización
    debe dejar AMBAS líneas marcadas, igual que una generación fresca."""
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila])
    svc.generar(Q, usuario_id=1)
    assert [l.es_duplicado for l in _lineas(db)] == [False]

    svc.externa.filas = [fila, dict(fila)]
    svc.generar(Q, usuario_id=1)

    assert [bool(l.es_duplicado) for l in _lineas(db)] == [True, True]


def test_flag_duplicado_se_apaga_al_borrar_la_copia(db):
    _concepto(db)
    fila = _fila()
    svc = _svc(db, [fila, dict(fila)])
    svc.generar(Q, usuario_id=1)
    assert [bool(l.es_duplicado) for l in _lineas(db)] == [True, True]

    svc.externa.filas = [fila]
    svc.generar(Q, usuario_id=1)

    lineas = _lineas(db)
    assert len(lineas) == 1
    assert bool(lineas[0].es_duplicado) is False


def test_valor_con_tres_decimales_no_churnea(db):
    """El campo puede mandar '12.985' (3 decimales); la columna DECIMAL(10,2)
    redondea half-up a 12.99 pero el formateo por float daba '12.98': la clave
    nunca coincidía y la línea se borraba y reinsertaba en CADA actualización
    (perdiendo id y conceptos manuales). Caso real: ORELLANA 2026-08-19."""
    _concepto(db)
    fila = _fila()
    fila["unidades"] = "12.985"
    svc = _svc(db, [fila])
    svc.generar(Q, usuario_id=1)
    # La columna debe quedar YA cuantizada como MySQL (12.99): sin esto, en
    # SQLite este test era una tautología (guardaba 12.985 crudo y ambos
    # lados de la clave coincidían aunque el código estuviera roto).
    assert _lineas(db)[0].unidades == Decimal("12.99")
    ids_antes = [l.id for l in _lineas(db)]

    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 0
    assert r["insertadas"] == 0
    assert [l.id for l in _lineas(db)] == ids_antes


def test_no_churnea_contra_columna_redondeada_por_mysql(db):
    """Simula el dato legacy real: la columna ya tiene el valor que MySQL
    redondeó (12.99) mientras el campo sigue mandando '12.985'."""
    _concepto(db)
    fila = _fila()
    fila["unidades"] = "12.985"
    svc = _svc(db, [fila])
    svc.generar(Q, usuario_id=1)
    linea = _lineas(db)[0]
    # fuerza el estado que MySQL dejó en producción
    db.execute(__import__("sqlalchemy").text(
        "UPDATE preliquidacion_linea SET unidades = 12.99 WHERE id = :i"
    ), {"i": linea.id})
    db.commit()

    r = svc.generar(Q, usuario_id=1)

    assert r["eliminadas"] == 0
    assert r["insertadas"] == 0


def test_normalizacion_redondea_half_up_como_mysql():
    from app.services.preliquidacion_service import _n
    assert _n("12.985") == "12.99"   # float lo bajaba a 12.98
    assert _n("12.984") == "12.98"
    assert _n(Decimal("12.985")) == "12.99"
    assert _n(8) == "8.00"
    assert _n(None) == "None"
    assert _n("no numerico") == "None"
    # MySQL no tiene cero negativo: '-0.001' debe normalizar a '0.00'
    assert _n("-0.001") == "0.00"
    # NaN/inf no son valores: mismos 'None' que un no-numérico
    assert _n(float("nan")) == "None"
    assert _n(float("inf")) == "None"


def test_to_decimal_normaliza_cero_negativo_y_nan(db):
    svc = PreliquidacionService(db)
    assert str(svc._to_decimal("-0.001")) == "0.00"
    assert svc._to_decimal(float("nan")) is None
    assert svc._to_decimal(None) is None


def test_detectar_duplicados_normaliza_igual_que_la_clave():
    """'12.985' y '12.99' son el mismo valor guardado: deben colapsar como
    duplicado igual que colapsan en la clave del diff."""
    from app.services.motor_reglas import MotorReglas
    base = _fila()
    f1 = dict(base, unidades="12.985")
    f2 = dict(base, unidades="12.99")
    dup = MotorReglas(None, None).detectar_duplicados([f1, f2])
    assert dup == {0, 1}


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
