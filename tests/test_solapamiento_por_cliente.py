"""Solapamiento por cliente (CONTEXT.md): una regla POR CLIENTE y una o más
ESPECÍFICAS del mismo cliente, misma tarea y quincena, matchean las mismas
líneas y SUMAN (ADR-0011). No es error del modelo: el sistema lo hace visible
y pide confirmación. La categoría participa (categorías explícitas distintas
no solapan); el código coincidente es agravante, no condición.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    CategoriaOperario, UnidadBaseConcepto, TipoConcepto,
)
from app.services.solapamiento_service import (
    categorias_compatibles, detectar_solapamiento_candidato,
)

Q = date(2026, 8, 16)
TAREA = "ENANCHADOR BOLSONES HORAS - CARGA"
CLIENTE = "CITRUSVIL"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=Q):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea=TAREA, cliente=CLIENTE, finca="EL CEIBAL", cuil="20-1-1",
           supervisor=None, hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        nombre_supervisor=supervisor, cuit=cuil,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena=Q, tarea=TAREA, cliente=None, finca=None, supervisor=None,
              codigo=461, precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              reemplaza_comun=True, categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        supervisor_nombre=supervisor, codigo=codigo, unidad_base=unidad, precio=precio,
        tipo=TipoConcepto.OTRO, reemplaza_comun=reemplaza_comun, categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _candidato_por_cliente(db, codigo=461, categoria=None, cliente=CLIENTE, tarea=TAREA):
    return detectar_solapamiento_candidato(
        db, quincena=Q, tarea_nombre=tarea, cliente_nombre=cliente,
        finca_nombre=None, supervisor_nombre=None, codigo=codigo, categoria=categoria,
    )


# ─── categorías ───────────────────────────────────────────────────────────────

def test_categorias_compatibles():
    assert categorias_compatibles(None, None)
    assert categorias_compatibles(None, 3)
    assert categorias_compatibles(3, None)
    assert categorias_compatibles(3, 3)
    assert not categorias_compatibles(3, 5)


# ─── candidato POR CLIENTE sobre específicas existentes (el caso real) ────────

def test_por_cliente_sobre_cinco_especificas_mismo_codigo(db):
    preliq = _preliq(db)
    fincas = ["EL CEIBAL", "LA RAMADA", "SAN JOSE", "LOS NOGALES", "EL TIMBO"]
    for f in fincas:
        _concepto(db, cliente=CLIENTE, finca=f, codigo=461)
    # 3 líneas en fincas con específica + 1 en la finca nueva (sin regla)
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-2")
    _linea(db, preliq, finca="LA RAMADA", cuil="20-1-3")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-4")

    s = _candidato_por_cliente(db, codigo=461)

    assert s is not None
    assert s["direccion"] == "por_cliente_sobre_especificos"
    assert s["tarea_nombre"] == TAREA and s["cliente_nombre"] == CLIENTE
    assert s["reglas_por_cliente"] == []            # el candidato no existe todavía
    assert sorted(s["fincas"]) == sorted(fincas)
    assert len(s["especificos"]) == 5
    assert all(e["mismo_codigo"] for e in s["especificos"])
    assert s["codigos_coincidentes"] == [461]
    assert s["lineas_afectadas"] == 3               # LA NUEVA no cuenta: no tiene específica


def test_por_cliente_con_codigo_distinto_alerta_sin_agravante(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=520)

    assert s is not None
    assert s["codigos_coincidentes"] == []
    assert s["especificos"][0]["mismo_codigo"] is False


def test_por_cliente_sin_especificas_no_solapa(db):
    _preliq(db)
    _concepto(db, codigo=461)                                   # común
    _concepto(db, supervisor="PEREZ", codigo=461)               # por supervisor
    _concepto(db, cliente="OTRO CLIENTE", finca="X", codigo=461)  # otro cliente

    assert _candidato_por_cliente(db, codigo=461) is None


def test_por_cliente_normaliza_mayusculas_y_espacios(db):
    _preliq(db)
    _concepto(db, tarea=TAREA.lower(), cliente=" citrusvil ", finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=461, cliente="CITRUSVIL", tarea=TAREA)

    assert s is not None
    assert s["fincas"] == ["EL CEIBAL"]


def test_sin_preliquidacion_generada_alerta_igual_con_cero_lineas(db):
    # Sin Preliquidacion para la quincena: la alerta sale (el maestro se
    # hereda) pero lineas_afectadas es 0.
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=461)

    assert s is not None
    assert s["lineas_afectadas"] == 0
