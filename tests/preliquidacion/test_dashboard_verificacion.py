"""Tests de caracterización de PreliquidacionService.dashboard_verificacion
(PR3, paso 3.5).

Fijan el comportamiento actual, sin base real (SQLite en memoria). Todos los
datos de personas son ficticios.

Nota: dashboard_verificacion **no** excluye a los empleados mensualizados;
lo hace el front (Verificacion.jsx). Es el comportamiento actual y PR4 no lo
cambia (el front pasa a filtrar por el campo `mensualizado` de la línea). No
se fija con un test propio para no atar este archivo a la constante que PR4
va a borrar.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import Preliquidacion, PreliquidacionLinea
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def svc(db):
    return PreliquidacionService(db)


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, legajo="0001", nombre_empleado="PERSONA UNO",
           fecha_tarea=date(2026, 5, 2), **extra):
    datos = dict(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit="20000000001", nombre_empleado=nombre_empleado,
        legajo_campo=legajo, legajo_asignado=legajo,
        empresa_asignada="LA ASTURIANA", fecha_tarea=fecha_tarea,
        # Línea "limpia" por defecto: el modelo trae linea_incompleta=True
        # como default, así que hay que apagarlo explícitamente.
        es_duplicado=False, alerta_legajo=False, alerta_empresa=False, linea_incompleta=False,
        hsjornal=Decimal("0"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    datos.update(extra)
    l = PreliquidacionLinea(**datos)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


# ─── Existencia ───────────────────────────────────────────────────────────────

def test_preliquidacion_inexistente_levanta_value_error(svc):
    with pytest.raises(ValueError, match="Preliquidacion 999 no encontrada"):
        svc.dashboard_verificacion(999)


def test_preliquidacion_existente_sin_lineas_devuelve_listas_vacias(db, svc):
    p = _preliq(db)

    assert svc.dashboard_verificacion(p.id) == {
        "exceso_horas": [], "exceso_tancadas": [],
        "exceso_plantas": [], "resumen_empleados": [],
    }


def test_solo_mira_las_lineas_de_esa_preliquidacion(db, svc):
    p = _preliq(db)
    otra = _preliq(db, quincena=date(2026, 5, 16))
    _linea(db, otra, hsjornal=Decimal("20"))

    assert svc.dashboard_verificacion(p.id)["exceso_horas"] == []


# ─── Exceso de horas (> 13 por legajo y fecha) ────────────────────────────────

def test_exceso_horas_suma_lineas_del_mismo_legajo_y_fecha(db, svc):
    p = _preliq(db)
    l1 = _linea(db, p, hsjornal=Decimal("7"), nombre_tarea="TAREA A")
    l2 = _linea(db, p, hsjornal=Decimal("7"), nombre_tarea="TAREA B")

    exceso = svc.dashboard_verificacion(p.id)["exceso_horas"]

    assert len(exceso) == 1
    e = exceso[0]
    assert e["legajo"] == "0001"
    assert e["nombre_empleado"] == "PERSONA UNO"
    assert e["fecha"] == "2026-05-02"
    assert e["valor"] == 14.0
    assert [x["id"] for x in e["lineas"]] == [l1.id, l2.id]
    assert e["lineas"][0] == {
        "id": l1.id, "nombre_tarea": "TAREA A",
        "nombre_cliente": "CLIENTE A", "nombre_finca": "FINCA 1",
        "grupo_pago_aplicado": None,
        "hsjornal": 7.0, "tancadas": 0.0, "unidades": 0.0,
    }


def test_exceso_horas_13_exacto_no_entra(db, svc):
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("6.5"))
    _linea(db, p, hsjornal=Decimal("6.5"))

    assert svc.dashboard_verificacion(p.id)["exceso_horas"] == []


def test_exceso_horas_no_suma_fechas_distintas(db, svc):
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("8"), fecha_tarea=date(2026, 5, 2))
    _linea(db, p, hsjornal=Decimal("8"), fecha_tarea=date(2026, 5, 3))

    assert svc.dashboard_verificacion(p.id)["exceso_horas"] == []


def test_exceso_horas_no_suma_legajos_distintos(db, svc):
    p = _preliq(db)
    _linea(db, p, legajo="0001", hsjornal=Decimal("8"))
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS", hsjornal=Decimal("8"))

    assert svc.dashboard_verificacion(p.id)["exceso_horas"] == []


def test_exceso_horas_agrupa_por_legajo_asignado_o_legajo_campo(db, svc):
    # Sin legajo_asignado cae al legajo_campo: una línea con asignado "0001"
    # y otra con sólo campo "0001" son el mismo grupo.
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("7"))
    _linea(db, p, hsjornal=Decimal("7"), legajo_asignado=None, legajo_campo="0001")

    exceso = svc.dashboard_verificacion(p.id)["exceso_horas"]

    assert [(e["legajo"], e["valor"]) for e in exceso] == [("0001", 14.0)]


def test_exceso_horas_sin_legajo_ni_fecha_agrupa_con_clave_vacia(db, svc):
    # Comportamiento actual: legajo y fecha ausentes se convierten en "" y
    # todas esas líneas caen en el mismo grupo.
    p = _preliq(db)
    _linea(db, p, legajo=None, fecha_tarea=None, hsjornal=Decimal("7"), nombre_empleado="PERSONA UNO")
    _linea(db, p, legajo=None, fecha_tarea=None, hsjornal=Decimal("7"), nombre_empleado="PERSONA DOS")

    exceso = svc.dashboard_verificacion(p.id)["exceso_horas"]

    assert len(exceso) == 1
    assert exceso[0]["legajo"] == ""
    assert exceso[0]["fecha"] == ""
    assert exceso[0]["valor"] == 14.0
    # El nombre es el de la primera línea del grupo.
    assert exceso[0]["nombre_empleado"] == "PERSONA UNO"


def test_hsjornal_none_cuenta_como_cero(db, svc):
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("14"))
    _linea(db, p, hsjornal=None)

    exceso = svc.dashboard_verificacion(p.id)["exceso_horas"]

    assert exceso[0]["valor"] == 14.0
    assert exceso[0]["lineas"][1]["hsjornal"] == 0.0


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason=(
        "bug conocido: dashboard_verificacion agrupa sólo por número de legajo, "
        "y el legajo es único por empresa (CONTEXT.md), así que dos personas "
        "distintas con el mismo legajo en empresas distintas se suman como una; "
        "el fix va en una tarea aparte"
    ),
)
def test_mismo_legajo_en_empresas_distintas_no_se_mezcla(db, svc):
    p = _preliq(db)
    _linea(db, p, legajo="0001", nombre_empleado="PERSONA UNO", cuit="20000000001",
           empresa_asignada="LA ASTURIANA", hsjornal=Decimal("7"), importe_total=Decimal("100"))
    _linea(db, p, legajo="0001", nombre_empleado="PERSONA DOS", cuit="20000000002",
           empresa_asignada="PAMPLONA", hsjornal=Decimal("7"), importe_total=Decimal("100"))

    r = svc.dashboard_verificacion(p.id)

    # Hoy: exceso_horas trae un grupo de 14 hs y resumen_empleados una sola
    # fila con importe 200, a nombre de PERSONA UNO y empresa LA ASTURIANA.
    assert r["exceso_horas"] == []
    assert len(r["resumen_empleados"]) == 2


# ─── Exceso de tancadas (> 35) ────────────────────────────────────────────────

def test_exceso_tancadas_umbral_35(db, svc):
    p = _preliq(db)
    _linea(db, p, legajo="0001", tancadas=Decimal("20"))
    _linea(db, p, legajo="0001", tancadas=Decimal("16"))
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS", tancadas=Decimal("35"))

    exceso = svc.dashboard_verificacion(p.id)["exceso_tancadas"]

    assert [(e["legajo"], e["valor"]) for e in exceso] == [("0001", 36.0)]


# ─── Exceso de plantas (> 6000, sólo grupo de pago PLANTA) ────────────────────

def test_exceso_plantas_suma_solo_grupo_planta_case_y_trim(db, svc):
    p = _preliq(db)
    # 0001: 3000 + 3001 en PLANTA (una con minúsculas y espacios) = 6001 → entra.
    _linea(db, p, legajo="0001", grupo_pago_aplicado=" planta ", unidades=Decimal("3000"))
    _linea(db, p, legajo="0001", grupo_pago_aplicado="PLANTA", unidades=Decimal("3001"))
    # 0002: 4000 en PLANTA + 4000 en otro grupo = 4000 contadas → no entra.
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS",
           grupo_pago_aplicado="PLANTA", unidades=Decimal("4000"))
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS",
           grupo_pago_aplicado="BINS", unidades=Decimal("4000"))
    # 0003: unidades sin grupo de pago → no cuentan.
    _linea(db, p, legajo="0003", nombre_empleado="PERSONA TRES",
           grupo_pago_aplicado=None, unidades=Decimal("7000"))

    exceso = svc.dashboard_verificacion(p.id)["exceso_plantas"]

    assert [(e["legajo"], e["valor"]) for e in exceso] == [("0001", 6001.0)]
    # Las líneas del grupo guardan el grupo de pago tal cual vino.
    assert [x["grupo_pago_aplicado"] for x in exceso[0]["lineas"]] == [" planta ", "PLANTA"]


def test_exceso_plantas_6000_exacto_no_entra(db, svc):
    p = _preliq(db)
    _linea(db, p, grupo_pago_aplicado="PLANTA", unidades=Decimal("6000"))

    assert svc.dashboard_verificacion(p.id)["exceso_plantas"] == []


def test_una_linea_puede_estar_en_varios_excesos(db, svc):
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("14"), tancadas=Decimal("40"),
           grupo_pago_aplicado="PLANTA", unidades=Decimal("7000"))

    r = svc.dashboard_verificacion(p.id)

    assert [e["valor"] for e in r["exceso_horas"]] == [14.0]
    assert [e["valor"] for e in r["exceso_tancadas"]] == [40.0]
    assert [e["valor"] for e in r["exceso_plantas"]] == [7000.0]


# ─── Orden ────────────────────────────────────────────────────────────────────

def test_excesos_ordenados_por_valor_descendente(db, svc):
    p = _preliq(db)
    _linea(db, p, legajo="0001", hsjornal=Decimal("14"))
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS", hsjornal=Decimal("20"))
    _linea(db, p, legajo="0003", nombre_empleado="PERSONA TRES", hsjornal=Decimal("16"))

    exceso = svc.dashboard_verificacion(p.id)["exceso_horas"]

    assert [(e["legajo"], e["valor"]) for e in exceso] == [
        ("0002", 20.0), ("0003", 16.0), ("0001", 14.0),
    ]


# ─── Resumen por empleado ─────────────────────────────────────────────────────

def test_resumen_empleados_agrupa_por_legajo_y_cuenta_dias_distintos(db, svc):
    p = _preliq(db)
    l1 = _linea(db, p, fecha_tarea=date(2026, 5, 3), importe_total=Decimal("40"))
    l2 = _linea(db, p, fecha_tarea=date(2026, 5, 2), importe_total=Decimal("30"))
    # Misma fecha que l2 y sólo legajo de campo: mismo grupo, no suma día.
    l3 = _linea(db, p, fecha_tarea=date(2026, 5, 2), importe_total=Decimal("30"),
                legajo_asignado=None, legajo_campo="0001")

    resumen = svc.dashboard_verificacion(p.id)["resumen_empleados"]

    assert len(resumen) == 1
    r = resumen[0]
    assert r["legajo"] == "0001"
    assert r["nombre_empleado"] == "PERSONA UNO"
    assert r["empresa_asignada"] == "LA ASTURIANA"
    assert r["importe_total"] == 100.0
    assert r["dias_trabajados"] == 2
    assert r["importe_por_dia"] == 50.0
    # Líneas ordenadas por fecha_tarea ascendente (orden estable dentro del día).
    assert [x["id"] for x in r["lineas"]] == [l2.id, l3.id, l1.id]
    assert r["lineas"][2] == {
        "id": l1.id, "fecha_tarea": "2026-05-03",
        "nombre_tarea": "TAREA X", "nombre_cliente": "CLIENTE A",
        "nombre_finca": "FINCA 1", "hsjornal": 0.0, "importe_total": 40.0,
    }


def test_resumen_importe_por_dia_redondeado_a_2(db, svc):
    p = _preliq(db)
    _linea(db, p, fecha_tarea=date(2026, 5, 2), importe_total=Decimal("50"))
    _linea(db, p, fecha_tarea=date(2026, 5, 3), importe_total=Decimal("25"))
    _linea(db, p, fecha_tarea=date(2026, 5, 4), importe_total=Decimal("25"))

    r = svc.dashboard_verificacion(p.id)["resumen_empleados"][0]

    assert r["dias_trabajados"] == 3
    assert r["importe_por_dia"] == 33.33


def test_resumen_sin_fechas_da_cero_dias_y_cero_por_dia(db, svc):
    p = _preliq(db)
    l = _linea(db, p, fecha_tarea=None, importe_total=Decimal("80"))
    _linea(db, p, fecha_tarea=None, importe_total=None)

    r = svc.dashboard_verificacion(p.id)["resumen_empleados"][0]

    assert r["importe_total"] == 80.0
    assert r["dias_trabajados"] == 0
    assert r["importe_por_dia"] == 0
    assert r["lineas"][0]["id"] == l.id
    assert r["lineas"][0]["fecha_tarea"] is None
    assert r["lineas"][1]["importe_total"] == 0.0


def test_resumen_ordenado_por_importe_descendente(db, svc):
    p = _preliq(db)
    _linea(db, p, legajo="0001", importe_total=Decimal("100"))
    _linea(db, p, legajo="0002", nombre_empleado="PERSONA DOS", importe_total=Decimal("300"))
    _linea(db, p, legajo="0003", nombre_empleado="PERSONA TRES", importe_total=Decimal("200"))

    resumen = svc.dashboard_verificacion(p.id)["resumen_empleados"]

    assert [(r["legajo"], r["importe_total"]) for r in resumen] == [
        ("0002", 300.0), ("0003", 200.0), ("0001", 100.0),
    ]


def test_resumen_incluye_a_todos_aunque_no_tengan_excesos(db, svc):
    p = _preliq(db)
    _linea(db, p, hsjornal=Decimal("8"), importe_total=Decimal("10"))

    r = svc.dashboard_verificacion(p.id)

    assert r["exceso_horas"] == []
    assert [e["legajo"] for e in r["resumen_empleados"]] == ["0001"]
