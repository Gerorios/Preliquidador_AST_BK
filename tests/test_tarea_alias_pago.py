from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    UnidadBaseConcepto, TipoConcepto,
)
from app.modulos.preliquidacion.services.preliquidacion_service import (
    PreliquidacionService, TAREAS_ALIAS_PAGO, tarea_canonica, tareas_que_pagan_como,
)

TAREA_ALIAS = "MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)"
TAREA_CANONICA = "MANTENIMIENTOS MECANICOS (TALLERES)"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente="CLIENTE A", finca="FINCA 1",
           cuil="20111111119", hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        cuit=cuil,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"),
        hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena, tarea, cliente=None, finca=None, codigo=1,
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente,
        finca_nombre=finca, codigo=codigo, unidad_base=unidad, precio=precio,
        tipo=TipoConcepto.OTRO, categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _match(c):
    return {
        "tarea_nombre": c.tarea_nombre, "cliente_nombre": c.cliente_nombre,
        "finca_nombre": c.finca_nombre, "supervisor_nombre": c.supervisor_nombre,
    }


# ─── Helpers puros ───────────────────────────────────────────────────────────

def test_tarea_canonica_traduce_el_alias():
    assert tarea_canonica(TAREA_ALIAS) == TAREA_CANONICA
    assert tarea_canonica("  " + TAREA_ALIAS.lower() + " ") == TAREA_CANONICA
    assert tarea_canonica("COSECHA LIMON") == "COSECHA LIMON"
    assert tarea_canonica(None) == ""


def test_tareas_que_pagan_como_expande_el_inverso():
    assert tareas_que_pagan_como([TAREA_CANONICA]) == sorted(
        {TAREA_CANONICA, TAREA_ALIAS}
    )
    assert tareas_que_pagan_como(["COSECHA LIMON"]) == ["COSECHA LIMON"]
    assert tareas_que_pagan_como([]) == []


def test_el_mapa_esta_normalizado():
    for alias, canonica in TAREAS_ALIAS_PAGO.items():
        assert alias == alias.strip().upper()
        assert canonica == canonica.strip().upper()
        assert canonica not in TAREAS_ALIAS_PAGO  # sin cadenas alias→alias


# ─── Path de recálculo (_aplicar_conceptos_a_lineas) ─────────────────────────

def test_linea_alias_paga_con_el_comun_de_la_canonica(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, TAREA_ALIAS)
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    PreliquidacionService(db).recalcular_por_concepto(
        preliq.quincena, actual=_match(c))

    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("800")  # 8 hs × $100
    assert linea.nombre_tarea == TAREA_ALIAS      # el nombre real NO se toca


def test_linea_de_otra_tarea_no_se_contamina(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "COSECHA LIMON")
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    PreliquidacionService(db).recalcular_por_concepto(
        preliq.quincena, actual=_match(c))

    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")


# ─── Path de generación (_buscar_conceptos_cache) ────────────────────────────

def test_buscar_conceptos_cache_resuelve_el_alias(db):
    preliq = _preliq(db)
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))
    svc = PreliquidacionService(db)
    comunes, por_cliente, especificos, por_supervisor = \
        svc._cache_conceptos_quincena(preliq.quincena)
    cache = {
        "comunes": comunes, "por_cliente": por_cliente,
        "especificos": especificos, "por_supervisor": por_supervisor,
        "categoria_por_cuil": {},
    }

    reglas = svc._buscar_conceptos_cache(TAREA_ALIAS, "CLIENTE A", "FINCA 1",
                                         cache, cuil="20111111119")
    assert [r.id for r in reglas] == [c.id]


# ─── Impacto reactivo inverso ────────────────────────────────────────────────

def test_editar_concepto_de_la_canonica_recalcula_la_linea_alias(db):
    preliq = _preliq(db)
    linea_alias = _linea(db, preliq, TAREA_ALIAS)
    linea_canon = _linea(db, preliq, TAREA_CANONICA, cuil="20222222227")
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    svc = PreliquidacionService(db)
    r = svc.recalcular_por_concepto(preliq.quincena, actual=_match(c))
    assert r["lineas_afectadas"] == 2  # la canónica Y la alias

    c.precio = Decimal("200")
    db.commit()
    svc.recalcular_por_concepto(preliq.quincena, actual=_match(c))

    db.refresh(linea_alias)
    db.refresh(linea_canon)
    assert linea_alias.importe_total == Decimal("1600")  # 8 × 200
    assert linea_canon.importe_total == Decimal("1600")


# ─── Mantenimiento: líneas alias = líneas de taller ─────────────────────────

def test_persona_con_solo_horas_guardia_aparece_en_operarios(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cuil="20111111119")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"), categoria=3)

    ops = PreliquidacionService(db).operarios_mantenimiento(preliq.id)
    assert [o["cuil"] for o in ops] == ["20111111119"]


def test_cambiar_categoria_recalcula_la_linea_alias(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, TAREA_ALIAS, cuil="20111111119")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"), categoria=3)
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("250"), categoria=4)

    svc = PreliquidacionService(db)
    svc.set_categoria_operario(preliq.id, "20111111119", 3)
    db.refresh(linea)
    assert linea.importe_total == Decimal("800")   # 8 × 100

    svc.set_categoria_operario(preliq.id, "20111111119", 4)
    db.refresh(linea)
    assert linea.importe_total == Decimal("2000")  # 8 × 250


# ─── API de precios ──────────────────────────────────────────────────────────

from fastapi import HTTPException
from app.modulos.preliquidacion.api.precios import crear_concepto, conceptos_faltantes
from app.modulos.preliquidacion.schemas import ConceptoUnifRequest


def test_crear_concepto_para_tarea_alias_da_422(db):
    datos = ConceptoUnifRequest(
        quincena=date(2026, 5, 1), tarea_nombre=TAREA_ALIAS,
        codigo=50, precio=Decimal("100"),
        unidad_base=UnidadBaseConcepto.HSJORNAL,
    )
    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos, db)
    assert exc.value.status_code == 422
    assert TAREA_CANONICA in exc.value.detail


def test_faltantes_muestra_el_combo_alias_como_canonica(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cliente="CLIENTE A", finca="FINCA 1")

    faltantes = conceptos_faltantes(preliq.quincena, db)
    assert {(f["tarea_nombre"], f["cliente_nombre"]) for f in faltantes} == {
        (TAREA_CANONICA, "CLIENTE A")
    }


def test_faltantes_no_lista_el_alias_si_la_canonica_tiene_concepto(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cliente="CLIENTE A", finca="FINCA 1")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"))

    faltantes = conceptos_faltantes(preliq.quincena, db)
    assert faltantes == []
