"""Concepto extra (ADR-0015): agregar por código un plus de otra tarea.

A2: reglas elegibles, opciones y representante. A3: sin precio y elección de
opción en agregar_concepto_por_codigo. A4: descripción e importes exactos. A5:
código repetido en la línea. SQLite en memoria; todos los datos son ficticios.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    ConceptoAdicional, ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea,
    TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.services import preliquidacion_service as servicio
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
CODIGO = 461
USUARIO = 7


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _regla(db, tarea, precio=Decimal("1000"), unidad=UnidadBaseConcepto.HSJORNAL,
           tipo=TipoConcepto.REMUNERATIVO, quincena=Q1, codigo=CODIGO, **extra):
    r = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, codigo=codigo,
        unidad_base=unidad, precio=precio, tipo=tipo, **extra,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _base(db):
    """A (TAREA B) y B (TAREA A) con la misma opción; C (TAREA C) con otra."""
    a = _regla(db, "TAREA B")
    b = _regla(db, "TAREA A")
    c = _regla(db, "TAREA C", precio=Decimal("5000"), unidad=UnidadBaseConcepto.FIJO)
    return a, b, c


def _ids(reglas):
    return {r.id for r in reglas}


def test_dos_opciones_ordenadas_por_precio_sin_tipo(db):
    a, b, c = _base(db)
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)
    opciones = svc._opciones_extra(reglas)

    assert _ids(reglas) == {a.id, b.id, c.id}
    assert opciones == [
        {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
        {"precio": "5000.0000", "unidad_base": "fijo", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
    ]


def test_representante_de_la_opcion_es_la_primera_tarea_alfabetica(db):
    a, b, c = _base(db)
    svc = PreliquidacionService(db)
    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)

    de_1000 = svc._reglas_de_opcion(reglas, "1000.0000", "hsjornal", "REMUNERATIVO")
    de_5000 = svc._reglas_de_opcion(reglas, Decimal("5000"), UnidadBaseConcepto.FIJO,
                                    TipoConcepto.REMUNERATIVO)

    assert _ids(de_1000) == {a.id, b.id}
    assert svc._representante(de_1000).id == b.id
    assert _ids(de_5000) == {c.id}
    assert svc._representante(de_5000).id == c.id


def test_opcion_inexistente_no_tiene_reglas(db):
    _base(db)
    svc = PreliquidacionService(db)
    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)

    assert svc._reglas_de_opcion(reglas, "1000", "fijo", "REMUNERATIVO") == []
    assert svc._reglas_de_opcion(reglas, "1000", "hsjornal", "NO_REMUNERATIVO") == []


def test_mismo_precio_y_unidad_con_otro_tipo_muestra_el_tipo(db):
    _base(db)
    d = _regla(db, "TAREA D", tipo=TipoConcepto.NO_REMUNERATIVO)
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)
    opciones = svc._opciones_extra(reglas)

    assert opciones == [
        {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "NO_REMUNERATIVO",
         "mostrar_tipo": True},
        {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO",
         "mostrar_tipo": True},
        {"precio": "5000.0000", "unidad_base": "fijo", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
    ]
    de_d = svc._reglas_de_opcion(reglas, "1000", "hsjornal", "NO_REMUNERATIVO")
    assert _ids(de_d) == {d.id}


def test_sin_precio_y_con_categoria_no_son_elegibles_ni_aportan_opcion(db):
    a, b, c = _base(db)
    # Tareas que irían primeras por orden alfabético: si fueran elegibles,
    # serían representantes.
    sin_precio = _regla(db, "TAREA 0", precio=None)
    con_categoria = _regla(db, "AAA", precio=Decimal("777"), categoria=3)
    con_categoria_misma_opcion = _regla(db, "AAB", categoria=4)
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)
    opciones = svc._opciones_extra(reglas)

    assert _ids(reglas) == {a.id, b.id, c.id}
    assert sin_precio.id not in _ids(reglas)
    assert {con_categoria.id, con_categoria_misma_opcion.id}.isdisjoint(_ids(reglas))
    assert [o["precio"] for o in opciones] == ["1000.0000", "5000.0000"]
    de_1000 = svc._reglas_de_opcion(reglas, "1000", "hsjornal", "REMUNERATIVO")
    assert svc._representante(de_1000).id == b.id


def test_desempate_por_cliente_sin_cliente_antes_que_acme(db):
    # ACME se crea primero (id menor) para que el id no decida.
    acme = _regla(db, "TAREA A", cliente_nombre="ACME")
    sin_cliente = _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)

    assert _ids(reglas) == {acme.id, sin_cliente.id}
    assert svc._representante(reglas).id == sin_cliente.id


def test_representante_normaliza_la_tarea(db):
    # Sin strip/upper, " tarea z" iría antes que "TAREA Y" por el espacio.
    _regla(db, " tarea z")
    y = _regla(db, "TAREA Y")
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)

    assert svc._representante(reglas).id == y.id


def test_otra_quincena_u_otro_codigo_no_entran(db):
    a, b, c = _base(db)
    _regla(db, "AAA", quincena=Q2, precio=Decimal("9000"))
    _regla(db, "AAA", codigo=902, precio=Decimal("8000"))
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)
    opciones = svc._opciones_extra(reglas)

    assert _ids(reglas) == {a.id, b.id, c.id}
    assert [o["precio"] for o in opciones] == ["1000.0000", "5000.0000"]


def test_sin_reglas_elegibles_no_hay_opciones(db):
    _regla(db, "TAREA A", precio=None)
    svc = PreliquidacionService(db)

    reglas = svc._reglas_elegibles_extra(Q1, CODIGO)

    assert reglas == []
    assert svc._opciones_extra(reglas) == []


# ─── A3: agregar_concepto_por_codigo elige la opción ─────────────────────────

def _preliq(db, quincena=Q1):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, **extra):
    datos = dict(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA Z", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit="20000000001", nombre_empleado="PERSONA UNO", legajo_campo="0001",
        empresa_asignada="LA ASTURIANA", legajo_asignado="0001",
        fecha_tarea=date(2026, 5, 2),
        # El modelo trae linea_incompleta=True por default: se apaga explícito.
        es_duplicado=False, alerta_legajo=False, alerta_empresa=False, linea_incompleta=False,
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    datos.update(extra)
    linea = PreliquidacionLinea(**datos)
    db.add(linea)
    db.commit()
    db.refresh(linea)
    return linea


def _importe_total(db, linea_id):
    db.expire_all()
    return db.get(PreliquidacionLinea, linea_id).importe_total


def test_por_codigo_solo_reglas_con_categoria_no_tiene_precio(db):
    linea = _linea(db, _preliq(db))
    _regla(db, "TAREA A", categoria=3)
    _regla(db, "TAREA B", precio=Decimal("5000"), categoria=4)
    svc = PreliquidacionService(db)

    with pytest.raises(ValueError, match="El código 461 no tiene precio cargado en esta quincena"):
        svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)
    assert db.query(ConceptoAdicional).count() == 0


def test_por_codigo_dos_opciones_sin_elegir_pide_opcion_y_no_escribe(db):
    linea = _linea(db, _preliq(db), importe_total=Decimal("100.00"))
    _base(db)
    svc = PreliquidacionService(db)

    with pytest.raises(servicio.ExtraRequiereOpcion) as exc:
        svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert exc.value.codigo == CODIGO
    assert len(exc.value.opciones) == 2
    assert [o["precio"] for o in exc.value.opciones] == ["1000.0000", "5000.0000"]
    assert db.query(ConceptoAdicional).count() == 0
    assert _importe_total(db, linea.id) == Decimal("100.00")


def test_por_codigo_opcion_inexistente_ya_no_esta_disponible(db):
    linea = _linea(db, _preliq(db))
    _base(db)
    svc = PreliquidacionService(db)
    opcion = {"precio": "1000.0000", "unidad_base": "fijo", "tipo": "REMUNERATIVO"}

    with pytest.raises(
        ValueError,
        match="La opción elegida ya no está disponible para el código 461 en esta quincena",
    ):
        svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO, opcion=opcion)
    assert db.query(ConceptoAdicional).count() == 0


def test_por_codigo_una_sola_opcion_se_agrega_directo_atada_a_la_representante(db):
    linea = _linea(db, _preliq(db))
    _regla(db, "TAREA C")
    b = _regla(db, "TAREA B")
    # Irían primeras por orden alfabético, pero no son elegibles.
    _regla(db, "TAREA 0", precio=None)
    _regla(db, "AAA", categoria=3)
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert concepto.concepto_liquidacion_id == b.id
    assert concepto.precio == Decimal("1000")
    assert concepto.unidad_base == "hsjornal"
    assert concepto.importe == Decimal("8000.00")  # 8 × 1000
    assert concepto.ingresado_por == USUARIO
    assert db.query(ConceptoAdicional).count() == 1
    assert _importe_total(db, linea.id) == Decimal("8000.00")


@pytest.mark.parametrize("como_objeto", [False, True])
def test_por_codigo_con_opcion_elegida_entre_dos(db, como_objeto):
    linea = _linea(db, _preliq(db))
    a, b, c = _base(db)
    svc = PreliquidacionService(db)
    datos = {"precio": "5000", "unidad_base": "fijo", "tipo": "REMUNERATIVO"}
    opcion = SimpleNamespace(**datos) if como_objeto else datos

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO, opcion=opcion)

    assert concepto.concepto_liquidacion_id == c.id
    assert concepto.precio == Decimal("5000")
    assert concepto.unidad_base == "fijo"
    assert concepto.importe == Decimal("5000.00")
    assert db.query(ConceptoAdicional).count() == 1


def test_por_codigo_opcion_compartida_se_ata_a_la_representante(db):
    linea = _linea(db, _preliq(db))
    a, b, c = _base(db)
    svc = PreliquidacionService(db)
    opcion = {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO"}

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO, opcion=opcion)

    # A (TAREA B) y B (TAREA A) ofrecen la opción: va a B por orden alfabético.
    assert concepto.concepto_liquidacion_id == b.id
    assert concepto.importe == Decimal("8000.00")


# ─── A4: descripción e importes exactos del extra ────────────────────────────

def _concepto_previo(db, linea, importe="100.00"):
    c = ConceptoAdicional(linea_id=linea.id, descripcion="Concepto previo", importe=Decimal(importe))
    db.add(c)
    linea.importe_total = (linea.importe_total or Decimal("0")) + Decimal(importe)
    db.commit()
    return c


@pytest.mark.parametrize(
    "hsjornal, precio, unidad, tipo, cantidad, importe",
    [
        ("8", "1250.50", UnidadBaseConcepto.HSJORNAL, TipoConcepto.REMUNERATIVO,
         Decimal("8"), Decimal("10004.00")),
        ("8", "5000", UnidadBaseConcepto.FIJO, TipoConcepto.NO_REMUNERATIVO,
         Decimal("1"), Decimal("5000.00")),
        ("4", "3000", UnidadBaseConcepto.JORNAL_TOPE1, TipoConcepto.REMUNERATIVO,
         Decimal("0.5"), Decimal("1500.00")),
        # 11,25 / 10 = 1,125 → ROUND_HALF_UP a 2 decimales (motor_reglas) → 1,13.
        ("11.25", "1000", UnidadBaseConcepto.JORNAL_TOPE1_MAS_EXCEDENTE,
         TipoConcepto.REMUNERATIVO, Decimal("1.13"), Decimal("1130.00")),
    ],
    ids=["hsjornal", "fijo", "jornal_tope1", "jornal_tope1_mas_excedente"],
)
def test_por_codigo_importe_exacto_y_descripcion_de_la_representante(
    db, hsjornal, precio, unidad, tipo, cantidad, importe,
):
    linea = _linea(db, _preliq(db), hsjornal=Decimal(hsjornal))
    _concepto_previo(db, linea, "100.00")
    # Dos reglas con la opción (TAREA B con el id menor, para que no decida el
    # id) y otra opción para que haga falta elegir.
    _regla(db, "TAREA B", precio=Decimal(precio), unidad=unidad, tipo=tipo)
    representante = _regla(db, "TAREA A", precio=Decimal(precio), unidad=unidad, tipo=tipo)
    _regla(db, "TAREA C", precio=Decimal("7"), unidad=UnidadBaseConcepto.UNIDADES)
    svc = PreliquidacionService(db)
    opcion = {"precio": precio, "unidad_base": unidad.value, "tipo": tipo.value}

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO, opcion=opcion)

    assert concepto.concepto_liquidacion_id == representante.id
    assert concepto.codigo_concepto == CODIGO
    assert concepto.precio == Decimal(precio)
    assert concepto.unidad_base == unidad.value
    assert concepto.tipo == tipo
    assert concepto.cantidad == cantidad
    assert concepto.importe == importe
    assert concepto.ingresado_por == USUARIO
    assert concepto.descripcion == "Concepto 461 (extra, de TAREA A)"
    assert _importe_total(db, linea.id) == Decimal("100.00") + importe


def test_descripcion_extra_usa_la_tarea_completa_sin_espacios_de_borde(db):
    tarea = "  COSECHA MANUAL DE UVA EN ESPALDERO ALTO CON TIJERA Y BINS  "
    linea = _linea(db, _preliq(db))
    _regla(db, tarea)
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert concepto.descripcion == (
        "Concepto 461 (extra, de COSECHA MANUAL DE UVA EN ESPALDERO ALTO CON TIJERA Y BINS)"
    )
    otra = _regla(db, " tarea z ", codigo=902)
    assert svc._descripcion_extra(otra) == "Concepto 902 (extra, de tarea z)"


def test_descripcion_extra_se_corta_al_largo_de_la_columna(db):
    # tarea_nombre admite 200 y descripcion 150: SQLite no hace cumplir el
    # largo, así que se mide acá.
    tarea = "T" * 190
    linea = _linea(db, _preliq(db))
    _regla(db, tarea)
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert len(concepto.descripcion) == 150
    assert concepto.descripcion.startswith("Concepto 461 (extra, de ")
    assert concepto.descripcion == ("Concepto 461 (extra, de " + tarea)[:150]


# ─── A5: código repetido en la línea ─────────────────────────────────────────

def _previo_con_codigo(db, linea, codigo=CODIGO, ingresado_por=None, importe="100.00"):
    """Un concepto previo con código: automático (ingresado_por None) o extra."""
    c = ConceptoAdicional(
        linea_id=linea.id, descripcion=f"Concepto {codigo}", codigo_concepto=codigo,
        importe=Decimal(importe), ingresado_por=ingresado_por,
    )
    db.add(c)
    linea.importe_total = (linea.importe_total or Decimal("0")) + Decimal(importe)
    db.commit()
    return c


@pytest.mark.parametrize("ingresado_por", [None, USUARIO], ids=["automatico", "extra"])
def test_por_codigo_repetido_frena_sin_escribir(db, ingresado_por):
    linea = _linea(db, _preliq(db))
    _previo_con_codigo(db, linea, ingresado_por=ingresado_por)
    _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    with pytest.raises(servicio.ExtraCodigoRepetido) as exc:
        svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert exc.value.detalle == {
        "tipo": "codigo_repetido",
        "mensaje": "La línea ya tiene el código 461.",
        "codigo": CODIGO,
        "lineas_con_codigo": 1,
        "total_lineas": 1,
    }
    assert db.query(ConceptoAdicional).count() == 1
    assert _importe_total(db, linea.id) == Decimal("100.00")


def test_por_codigo_repetido_con_dos_opciones_pide_opcion_primero(db):
    linea = _linea(db, _preliq(db))
    _previo_con_codigo(db, linea)
    _base(db)
    svc = PreliquidacionService(db)

    with pytest.raises(servicio.ExtraRequiereOpcion):
        svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)
    with pytest.raises(servicio.ExtraCodigoRepetido):
        svc.agregar_concepto_por_codigo(
            linea.id, CODIGO, USUARIO,
            opcion={"precio": "5000", "unidad_base": "fijo", "tipo": "REMUNERATIVO"},
        )
    assert db.query(ConceptoAdicional).count() == 1
    assert _importe_total(db, linea.id) == Decimal("100.00")


def test_por_codigo_repetido_confirmado_se_agrega_y_suma(db):
    linea = _linea(db, _preliq(db))
    _previo_con_codigo(db, linea)
    _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(
        linea.id, CODIGO, USUARIO, confirmar_repetido=True,
    )

    assert concepto.importe == Decimal("8000.00")
    assert db.query(ConceptoAdicional).count() == 2
    assert _importe_total(db, linea.id) == Decimal("8100.00")


def test_por_codigo_manual_libre_no_cuenta_como_repetido(db):
    linea = _linea(db, _preliq(db))
    _concepto_previo(db, linea, "100.00")  # sin codigo_concepto
    _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert concepto.importe == Decimal("8000.00")
    assert db.query(ConceptoAdicional).count() == 2
    assert _importe_total(db, linea.id) == Decimal("8100.00")


def test_por_codigo_otro_codigo_en_la_linea_no_cuenta_como_repetido(db):
    linea = _linea(db, _preliq(db))
    _previo_con_codigo(db, linea, codigo=902)
    _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert concepto.codigo_concepto == CODIGO
    assert db.query(ConceptoAdicional).count() == 2
    assert _importe_total(db, linea.id) == Decimal("8100.00")


def test_por_codigo_mismo_codigo_en_otra_linea_no_cuenta_como_repetido(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq)
    otra = _linea(db, preliq, nombre_empleado="PERSONA DOS", cuit="20000000002")
    _previo_con_codigo(db, otra)
    _regla(db, "TAREA A")
    svc = PreliquidacionService(db)

    concepto = svc.agregar_concepto_por_codigo(linea.id, CODIGO, USUARIO)

    assert concepto.linea_id == linea.id
    assert _importe_total(db, linea.id) == Decimal("8000.00")
