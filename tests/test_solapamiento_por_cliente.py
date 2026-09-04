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

from app.api.precios import copiar_quincena, crear_concepto, solapamientos_quincena
from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    CategoriaOperario, UnidadBaseConcepto, TipoConcepto,
)
from app.schemas.schemas import ConceptoUnifRequest
from app.services.preliquidacion_service import TAREAS_ALIAS_PAGO
from app.services.solapamiento_service import (
    categorias_compatibles, detectar_solapamiento_candidato, listar_solapamientos,
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


def _candidato_especifico(db, finca, codigo=461, categoria=None):
    return detectar_solapamiento_candidato(
        db, quincena=Q, tarea_nombre=TAREA, cliente_nombre=CLIENTE,
        finca_nombre=finca, supervisor_nombre=None, codigo=codigo, categoria=categoria,
    )


# ─── dirección inversa: candidato ESPECÍFICO sobre por cliente existente ─────

def test_especifico_sobre_por_cliente_existente(db):
    preliq = _preliq(db)
    pc = _concepto(db, cliente=CLIENTE, finca=None, codigo=461, precio=Decimal("900"))
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-1")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-2")
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-3")   # otra finca: no cuenta

    s = _candidato_especifico(db, finca="LA NUEVA", codigo=461)

    assert s is not None
    assert s["direccion"] == "especifico_sobre_por_cliente"
    assert [r["id"] for r in s["reglas_por_cliente"]] == [pc.id]
    assert Decimal(s["reglas_por_cliente"][0]["precio"]) == Decimal("900")
    assert s["especificos"] == []
    assert s["fincas"] == ["LA NUEVA"]
    assert s["codigos_coincidentes"] == [461]
    assert s["lineas_afectadas"] == 2


def test_especifico_sin_por_cliente_no_solapa(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)   # otra específica
    _concepto(db, codigo=461)                                        # común

    assert _candidato_especifico(db, finca="LA NUEVA") is None


# ─── categoría ───────────────────────────────────────────────────────────────

def test_categorias_explicitas_distintas_no_solapan(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)

    assert _candidato_por_cliente(db, codigo=461, categoria=5) is None


def test_categoria_null_contra_explicita_solapa_y_cuenta_solo_esa_categoria(db):
    preliq = _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)
    db.add_all([
        CategoriaOperario(quincena=Q, cuil="20-1-1", categoria=3),
        CategoriaOperario(quincena=Q, cuil="20-1-2", categoria=5),
    ])
    db.commit()
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")   # cat 3: cobra doble
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-2")   # cat 5: la específica no le aplica
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-3")   # sin categoría: la específica no le aplica

    s = _candidato_por_cliente(db, codigo=461, categoria=None)

    assert s is not None
    assert s["lineas_afectadas"] == 1


# ─── listado vigente ─────────────────────────────────────────────────────────

def test_listar_solapamientos_vacio_cuando_no_hay(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _concepto(db, cliente="OTRO", finca=None, codigo=461)   # por cliente de OTRO cliente

    assert listar_solapamientos(db, Q) == []


def test_listar_solapamientos_agrupa_por_tarea_y_cliente(db):
    preliq = _preliq(db)
    # Par 1: CITRUSVIL — 2 por cliente + 2 específicas, 1 específica incompatible por categoría
    pc1 = _concepto(db, cliente=CLIENTE, finca=None, codigo=461)
    pc2 = _concepto(db, cliente=CLIENTE, finca=None, codigo=520)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _concepto(db, cliente=CLIENTE, finca="LA RAMADA", codigo=700)
    _concepto(db, cliente=CLIENTE, finca="SAN JOSE", codigo=461, categoria=3)  # compatible: pc1 no tiene categoría
    # Par 2: otra tarea, mismo cliente, solo específicas → no aparece
    _concepto(db, tarea="OTRA TAREA", cliente=CLIENTE, finca="EL CEIBAL", codigo=1)
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")
    _linea(db, preliq, finca="LA RAMADA", cuil="20-1-2")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-3")

    lista = listar_solapamientos(db, Q)

    assert len(lista) == 1
    s = lista[0]
    assert (s["tarea_nombre"], s["cliente_nombre"]) == (TAREA, CLIENTE)
    assert s["direccion"] == "por_cliente_sobre_especificos"
    assert sorted(r["id"] for r in s["reglas_por_cliente"]) == sorted([pc1.id, pc2.id])
    assert sorted(s["fincas"]) == ["EL CEIBAL", "LA RAMADA", "SAN JOSE"]
    assert s["codigos_coincidentes"] == [461]
    assert [e["mismo_codigo"] for e in sorted(s["especificos"], key=lambda e: e["finca_nombre"])] == [True, False, True]
    assert s["lineas_afectadas"] == 2


def test_listar_solapamientos_excluye_especificas_incompatibles_por_categoria(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461, categoria=5)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)   # incompatible
    _concepto(db, cliente=CLIENTE, finca="LA RAMADA", codigo=461, categoria=5)   # compatible

    lista = listar_solapamientos(db, Q)

    assert len(lista) == 1
    assert lista[0]["fincas"] == ["LA RAMADA"]


def test_listar_solapamientos_ordena_por_tarea_y_cliente(db):
    _preliq(db)
    _concepto(db, tarea="ZETA", cliente="A", finca=None, codigo=1)
    _concepto(db, tarea="ZETA", cliente="A", finca="F", codigo=1)
    _concepto(db, tarea="ALFA", cliente="B", finca=None, codigo=1)
    _concepto(db, tarea="ALFA", cliente="B", finca="F", codigo=1)

    lista = listar_solapamientos(db, Q)

    assert [(s["tarea_nombre"], s["cliente_nombre"]) for s in lista] == [("ALFA", "B"), ("ZETA", "A")]


# ─── eje supervisor: nunca es solapamiento; supervisor vacío SÍ es eje cliente ─

def test_candidato_por_supervisor_no_solapa(db):
    # Ya existen una por cliente y una específica que sí solapan entre sí, pero
    # el candidato va por el eje supervisor: no participa.
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    s = detectar_solapamiento_candidato(
        db, quincena=Q, tarea_nombre=TAREA, cliente_nombre=None,
        finca_nombre=None, supervisor_nombre="PEREZ", codigo=461, categoria=None,
    )

    assert s is None


def test_por_cliente_con_supervisor_vacio_cuenta_como_eje_cliente(db):
    # supervisor_nombre = "" (no NULL) sigue siendo una regla del eje cliente:
    # matchea y suma, así que debe detectarse el solapamiento.
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, supervisor="", codigo=461)

    s = _candidato_especifico(db, finca="LA NUEVA", codigo=461)

    assert s is not None
    assert s["direccion"] == "especifico_sobre_por_cliente"
    assert len(s["reglas_por_cliente"]) == 1


# ─── casing y alias de pago ──────────────────────────────────────────────────

def test_fincas_conservan_el_casing_del_maestro(db):
    # `fincas` es texto para mostrar: respeta cómo está escrita la finca en el
    # maestro (igual que especificos[].finca_nombre). Las comparaciones
    # internas siguen siendo normalizadas.
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=" El Ceibal ", codigo=461)

    s = _candidato_por_cliente(db, codigo=461)

    assert s is not None
    assert s["fincas"] == ["El Ceibal"]


def test_alias_de_pago_cuenta_en_lineas_afectadas(db):
    # ADR-0012: una línea cargada con el alias paga con el maestro de la tarea
    # canónica, así que cobra doble igual y debe contarse.
    alias, canonica = next(iter(TAREAS_ALIAS_PAGO.items()))
    preliq = _preliq(db)
    _concepto(db, tarea=canonica, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _linea(db, preliq, tarea=alias, finca="EL CEIBAL", cuil="20-1-1")
    _linea(db, preliq, tarea=canonica, finca="EL CEIBAL", cuil="20-1-2")

    s = _candidato_por_cliente(db, codigo=461, tarea=canonica)

    assert s is not None
    assert s["lineas_afectadas"] == 2


def _req(cliente=CLIENTE, finca=None, codigo=461, categoria=None, confirmar=None):
    kwargs = dict(
        quincena=Q, tarea_nombre=TAREA, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("100"),
        tipo=TipoConcepto.OTRO, categoria=categoria,
    )
    if confirmar is not None:
        kwargs["confirmar_solapamiento"] = confirmar
    return ConceptoUnifRequest(**kwargs)


# ─── compuerta en el POST ────────────────────────────────────────────────────

def test_post_por_cliente_sobre_especificas_responde_409_y_no_crea(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    antes = db.query(ConceptoLiquidacion).count()

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(finca=None, codigo=461), db=db)

    assert exc.value.status_code == 409
    d = exc.value.detail
    assert d["tipo"] == "solapamiento_por_cliente"
    assert d["solapamiento"]["fincas"] == ["EL CEIBAL"]
    assert d["solapamiento"]["codigos_coincidentes"] == [461]
    assert db.query(ConceptoLiquidacion).count() == antes


def test_post_con_confirmar_solapamiento_crea_igual(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    nuevo = crear_concepto(datos=_req(finca=None, codigo=461, confirmar=True), db=db)

    assert nuevo.id is not None
    assert nuevo.cliente_nombre == CLIENTE and nuevo.finca_nombre is None


def test_post_especifico_sobre_por_cliente_responde_409(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461)

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(finca="LA NUEVA", codigo=461), db=db)

    assert exc.value.status_code == 409
    assert exc.value.detail["solapamiento"]["direccion"] == "especifico_sobre_por_cliente"


def test_post_sin_solapamiento_crea_sin_confirmar(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    # Específica para la finca nueva: el camino correcto, sin 409.
    nuevo = crear_concepto(datos=_req(finca="LA NUEVA", codigo=461), db=db)
    assert nuevo.finca_nombre == "LA NUEVA"

    # Común y por supervisor: nunca participan.
    comun = crear_concepto(datos=_req(cliente=None, finca=None, codigo=999), db=db)
    assert comun.cliente_nombre is None


def test_post_categorias_distintas_no_disparan_409(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)

    nuevo = crear_concepto(datos=_req(finca=None, codigo=461, categoria=5), db=db)
    assert nuevo.id is not None


def test_confirmar_solapamiento_default_false():
    assert _req().confirmar_solapamiento is False


def test_endpoint_solapamientos_devuelve_lista(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    lista = solapamientos_quincena(quincena=Q, db=db)

    assert len(lista) == 1
    assert lista[0]["cliente_nombre"] == CLIENTE


def test_copiar_informa_solapamientos_heredados(db):
    origen = date(2026, 8, 1)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca=None, codigo=461)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="LA RAMADA", codigo=461)

    r = copiar_quincena(quincena_origen=origen, quincena_destino=Q, db=db)

    assert r.solapamientos_heredados == 1
    assert "1 solapamiento" in (r.detalle or "")


def test_copiar_sin_solapamientos_informa_cero(db):
    origen = date(2026, 8, 1)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    r = copiar_quincena(quincena_origen=origen, quincena_destino=Q, db=db)

    assert r.solapamientos_heredados == 0
    assert "solapamiento" not in (r.detalle or "")
