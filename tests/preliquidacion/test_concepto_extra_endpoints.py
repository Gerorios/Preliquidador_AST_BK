"""Concepto extra (ADR-0015), A6: endpoint POST /api/preliquidacion/linea/
{linea_id}/conceptos/por-codigo con `opcion` y `confirmar_repetido`.

Contrato en el plan (docs/superpowers/plans/2026-09-30-concepto-extra.md, §3).
SQLite en memoria con TestClient; todos los datos son ficticios.
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
from app.main import app
from app.modulos.preliquidacion.models import (
    ConceptoAdicional, ConceptoLiquidacion, Preliquidacion, PreliquidacionLinea,
    TipoConcepto, UnidadBaseConcepto,
)

Q1 = date(2026, 5, 1)
CODIGO = 461
USUARIO = 7
CLAVES_OPCION = {"precio", "unidad_base", "tipo", "mostrar_tipo"}


def _url(linea_id):
    return f"/api/preliquidacion/linea/{linea_id}/conceptos/por-codigo"


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
        id=USUARIO, nombre="Admin Prueba", email="admin@ejemplo.test",
        rol="admin", activo=True, modulos=[],
    )
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    # get_service declara las 3 sesiones: todas apuntan a la sqlite.
    app.dependency_overrides[get_db_propia] = lambda: db
    app.dependency_overrides[get_db_externa] = lambda: db
    app.dependency_overrides[get_db_sueldos] = lambda: db
    # Sin `with`: no corre el lifespan (que verifica las conexiones reales).
    yield TestClient(app)
    app.dependency_overrides.clear()


def _linea(db, previo=None):
    """Línea de TAREA Z, 8 hs. Con `previo`, un concepto previo de 100 con ese
    código (None: sin concepto previo)."""
    p = Preliquidacion(quincena=Q1, creado_por=1)
    db.add(p)
    db.commit()
    l = PreliquidacionLinea(
        preliquidacion_id=p.id,
        nombre_tarea="TAREA Z", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit="20000000001", nombre_empleado="PERSONA UNO", legajo_campo="0001",
        empresa_asignada="LA ASTURIANA", legajo_asignado="0001",
        fecha_tarea=date(2026, 5, 2),
        es_duplicado=False, alerta_legajo=False, alerta_empresa=False, linea_incompleta=False,
        hsjornal=Decimal("8"), tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    db.add(l)
    db.commit()
    if previo is not None:
        db.add(ConceptoAdicional(
            linea_id=l.id, descripcion=f"Concepto {previo} (auto)",
            codigo_concepto=previo, importe=Decimal("100.00"),
        ))
        l.importe_total = Decimal("100.00")
        db.commit()
    db.refresh(l)
    return l


def _regla(db, tarea, precio=Decimal("1000"), unidad=UnidadBaseConcepto.HSJORNAL,
           tipo=TipoConcepto.REMUNERATIVO, codigo=CODIGO):
    r = ConceptoLiquidacion(
        quincena=Q1, tarea_nombre=tarea, codigo=codigo,
        unidad_base=unidad, precio=precio, tipo=tipo,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _dos_opciones(db):
    """(1000, hsjornal) en TAREA B y TAREA A; (5000, fijo) en TAREA C."""
    _regla(db, "TAREA B")
    _regla(db, "TAREA A")
    _regla(db, "TAREA C", precio=Decimal("5000"), unidad=UnidadBaseConcepto.FIJO)


def _total(db, linea_id):
    db.expire_all()
    return db.get(PreliquidacionLinea, linea_id).importe_total


def test_dos_opciones_sin_opcion_da_409_elegir_opcion_sin_escribir(db, cliente):
    linea = _linea(db)
    _dos_opciones(db)

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["tipo"] == "elegir_opcion"
    assert detail["mensaje"] == "El código 461 tiene 2 opciones en esta quincena: elegí una."
    assert detail["codigo"] == CODIGO
    assert detail["opciones"] == [
        {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
        {"precio": "5000.0000", "unidad_base": "fijo", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
    ]
    for op in detail["opciones"]:
        # Sin tareas, clientes, fincas ni supervisores: sólo la opción.
        assert set(op) == CLAVES_OPCION
        assert isinstance(op["precio"], str)
    assert db.query(ConceptoAdicional).count() == 0
    assert _total(db, linea.id) == Decimal("0")


def test_reintento_con_opcion_agrega_con_importe_exacto(db, cliente):
    linea = _linea(db)
    _dos_opciones(db)
    opcion = cliente.post(_url(linea.id), json={"codigo": CODIGO}).json()["detail"]["opciones"][0]
    opcion = {k: opcion[k] for k in ("precio", "unidad_base", "tipo")}

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO, "opcion": opcion})

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["descripcion"] == "Concepto 461 (extra, de TAREA A)"
    assert Decimal(cuerpo["importe"]) == Decimal("8000.00")  # 8 hs × 1000
    assert cuerpo["codigo_concepto"] == CODIGO
    assert cuerpo["unidad_base"] == "hsjornal"
    assert cuerpo["ingresado_por"] == USUARIO
    assert _total(db, linea.id) == Decimal("8000.00")


def test_opcion_con_precio_numerico_y_otra_opcion(db, cliente):
    """La opción viaja por valor: un precio sin decimales también la encuentra."""
    linea = _linea(db)
    _dos_opciones(db)

    r = cliente.post(_url(linea.id), json={
        "codigo": CODIGO,
        "opcion": {"precio": 5000, "unidad_base": "fijo", "tipo": "REMUNERATIVO"},
    })

    assert r.status_code == 200, r.text
    assert r.json()["descripcion"] == "Concepto 461 (extra, de TAREA C)"
    assert Decimal(r.json()["importe"]) == Decimal("5000.00")


def test_linea_con_el_codigo_da_409_codigo_repetido_y_con_flag_agrega(db, cliente):
    linea = _linea(db, previo=CODIGO)
    _regla(db, "TAREA A")

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["tipo"] == "codigo_repetido"
    assert detail["codigo"] == CODIGO
    assert detail["lineas_con_codigo"] == 1
    assert detail["total_lineas"] == 1
    assert detail["mensaje"]
    assert db.query(ConceptoAdicional).count() == 1
    assert _total(db, linea.id) == Decimal("100.00")

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO, "confirmar_repetido": True})

    assert r.status_code == 200, r.text
    assert Decimal(r.json()["importe"]) == Decimal("8000.00")
    assert db.query(ConceptoAdicional).count() == 2
    assert _total(db, linea.id) == Decimal("8100.00")


def test_codigo_con_reglas_sin_precio_da_404(db, cliente):
    linea = _linea(db)
    _regla(db, "TAREA A", precio=None)

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO})

    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "El código 461 no tiene precio cargado en esta quincena"
    assert db.query(ConceptoAdicional).count() == 0


def test_opcion_ya_no_disponible_da_404(db, cliente):
    linea = _linea(db)
    _dos_opciones(db)

    r = cliente.post(_url(linea.id), json={
        "codigo": CODIGO,
        "opcion": {"precio": "1234", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO"},
    })

    assert r.status_code == 404, r.text
    assert r.json()["detail"] == (
        "La opción elegida ya no está disponible para el código 461 en esta quincena"
    )
    assert db.query(ConceptoAdicional).count() == 0


def test_opcion_con_unidad_invalida_da_422(db, cliente):
    linea = _linea(db)
    _regla(db, "TAREA A")

    r = cliente.post(_url(linea.id), json={
        "codigo": CODIGO,
        "opcion": {"precio": "1000", "unidad_base": "xx", "tipo": "REMUNERATIVO"},
    })

    assert r.status_code == 422, r.text
    assert db.query(ConceptoAdicional).count() == 0


def test_body_viejo_con_una_opcion_agrega_directo(db, cliente):
    """Compatibilidad con el front actual: sólo {"codigo": N}."""
    linea = _linea(db)
    _regla(db, "TAREA B")
    _regla(db, "TAREA A")

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO})

    assert r.status_code == 200, r.text
    assert r.json()["descripcion"] == "Concepto 461 (extra, de TAREA A)"
    assert Decimal(r.json()["importe"]) == Decimal("8000.00")
    assert _total(db, linea.id) == Decimal("8000.00")


def test_linea_inexistente_da_404(db, cliente):
    _regla(db, "TAREA A")

    r = cliente.post(_url(999), json={"codigo": CODIGO})

    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Línea 999 no encontrada"


# ─── A10: endpoint masivo POST /api/preliquidacion/lineas/concepto-masivo ─────

URL_MASIVO = "/api/preliquidacion/lineas/concepto-masivo"


def _tres_lineas(db, con_codigo=0):
    """Tres líneas de TAREA Z en la misma quincena: 8 / 4 / 2.5 hs. Las
    primeras `con_codigo` traen un concepto previo de 100 con CODIGO."""
    p = Preliquidacion(quincena=Q1, creado_por=1)
    db.add(p)
    db.commit()
    lineas = []
    for i, hs in enumerate((Decimal("8"), Decimal("4"), Decimal("2.5")), start=1):
        l = PreliquidacionLinea(
            preliquidacion_id=p.id,
            nombre_tarea="TAREA Z", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
            cuit=f"2000000000{i}", nombre_empleado=f"PERSONA {i}", legajo_campo=f"000{i}",
            empresa_asignada="LA ASTURIANA", legajo_asignado=f"000{i}",
            fecha_tarea=date(2026, 5, 2),
            es_duplicado=False, alerta_legajo=False, alerta_empresa=False,
            linea_incompleta=False,
            hsjornal=hs, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
            importe_total=Decimal("0"),
        )
        db.add(l)
        db.commit()
        if i <= con_codigo:
            db.add(ConceptoAdicional(
                linea_id=l.id, descripcion=f"Concepto {CODIGO} (auto)",
                codigo_concepto=CODIGO, importe=Decimal("100.00"),
            ))
            l.importe_total = Decimal("100.00")
            db.commit()
        db.refresh(l)
        lineas.append(l)
    return lineas


def _extras(db):
    db.expire_all()
    return db.query(ConceptoAdicional).filter(
        ConceptoAdicional.ingresado_por.isnot(None)
    ).all()


def test_masivo_dos_opciones_sin_opcion_da_409_elegir_opcion_sin_escribir(db, cliente):
    lineas = _tres_lineas(db)
    _dos_opciones(db)

    r = cliente.post(URL_MASIVO, json={"linea_ids": [l.id for l in lineas], "codigo": CODIGO})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["tipo"] == "elegir_opcion"
    assert detail["mensaje"] == "El código 461 tiene 2 opciones en esta quincena: elegí una."
    assert detail["codigo"] == CODIGO
    assert detail["opciones"] == [
        {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
        {"precio": "5000.0000", "unidad_base": "fijo", "tipo": "REMUNERATIVO",
         "mostrar_tipo": False},
    ]
    assert db.query(ConceptoAdicional).count() == 0
    for l in lineas:
        assert _total(db, l.id) == Decimal("0")


def test_masivo_con_opcion_agrega_con_importe_exacto(db, cliente):
    lineas = _tres_lineas(db)
    _dos_opciones(db)

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO,
        "opcion": {"precio": "1000.0000", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO"},
    })

    assert r.status_code == 200, r.text
    assert r.json()["mensaje"] == "Concepto agregado"
    assert r.json()["detalle"] == "3 líneas actualizadas"
    esperados = (Decimal("8000.00"), Decimal("4000.00"), Decimal("2500.00"))
    extras = _extras(db)
    assert {c.linea_id: c.importe for c in extras} == {
        l.id: e for l, e in zip(lineas, esperados)
    }
    for c in extras:
        assert c.descripcion == "Concepto 461 (extra, de TAREA A)"
    for l, e in zip(lineas, esperados):
        assert _total(db, l.id) == e


def test_masivo_repetido_frenar_da_409_sin_escribir(db, cliente):
    lineas = _tres_lineas(db, con_codigo=2)
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={"linea_ids": [l.id for l in lineas], "codigo": CODIGO})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["tipo"] == "codigo_repetido"
    assert detail["codigo"] == CODIGO
    assert detail["lineas_con_codigo"] == 2
    assert detail["total_lineas"] == 3
    assert detail["mensaje"]
    assert db.query(ConceptoAdicional).count() == 2
    assert _extras(db) == []


def test_masivo_repetido_saltear_cuenta_las_salteadas(db, cliente):
    lineas = _tres_lineas(db, con_codigo=2)
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO, "si_repetido": "saltear",
    })

    assert r.status_code == 200, r.text
    assert r.json()["detalle"] == "1 líneas actualizadas · 2 salteadas"
    extras = _extras(db)
    assert [c.linea_id for c in extras] == [lineas[2].id]
    assert extras[0].importe == Decimal("2500.00")  # 2.5 hs × 1000
    assert _total(db, lineas[0].id) == Decimal("100.00")
    assert _total(db, lineas[1].id) == Decimal("100.00")
    assert _total(db, lineas[2].id) == Decimal("2500.00")


def test_masivo_repetido_saltear_una_dice_salteada_en_singular(db, cliente):
    lineas = _tres_lineas(db, con_codigo=1)
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO, "si_repetido": "saltear",
    })

    assert r.status_code == 200, r.text
    assert r.json()["detalle"] == "2 líneas actualizadas · 1 salteada"


def test_masivo_repetido_agregar_aplica_a_todas(db, cliente):
    lineas = _tres_lineas(db, con_codigo=2)
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO, "si_repetido": "agregar",
    })

    assert r.status_code == 200, r.text
    assert r.json()["detalle"] == "3 líneas actualizadas"
    assert len(_extras(db)) == 3
    assert _total(db, lineas[0].id) == Decimal("8100.00")
    assert _total(db, lineas[1].id) == Decimal("4100.00")
    assert _total(db, lineas[2].id) == Decimal("2500.00")


def test_masivo_si_repetido_invalido_da_422(db, cliente):
    lineas = _tres_lineas(db)
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO, "si_repetido": "otra",
    })

    assert r.status_code == 422, r.text
    assert db.query(ConceptoAdicional).count() == 0


def test_masivo_body_viejo_con_una_opcion_agrega_directo(db, cliente):
    """Compatibilidad con el front actual: sólo {"linea_ids", "codigo"}."""
    lineas = _tres_lineas(db)
    _regla(db, "TAREA B")
    _regla(db, "TAREA A")

    r = cliente.post(URL_MASIVO, json={"linea_ids": [l.id for l in lineas], "codigo": CODIGO})

    assert r.status_code == 200, r.text
    assert r.json()["detalle"] == "3 líneas actualizadas"
    assert len(_extras(db)) == 3
    assert _total(db, lineas[0].id) == Decimal("8000.00")


# ─── R1: precio de la opción fuera de Numeric(12, 4) ──────────────────────────

OPCION_PRECIO_ENORME = {"precio": "1e30", "unidad_base": "hsjornal", "tipo": "REMUNERATIVO"}


def test_opcion_con_precio_enorme_da_422_sin_escribir(db, cliente):
    """R1: un precio que no entra en Numeric(12, 4) es un 422, no un 500."""
    linea = _linea(db)
    _dos_opciones(db)

    r = cliente.post(_url(linea.id), json={"codigo": CODIGO, "opcion": OPCION_PRECIO_ENORME})

    assert r.status_code == 422, r.text
    assert db.query(ConceptoAdicional).count() == 0
    assert _total(db, linea.id) == Decimal("0")


def test_masivo_opcion_con_precio_enorme_da_422_sin_escribir(db, cliente):
    lineas = _tres_lineas(db)
    _dos_opciones(db)

    r = cliente.post(URL_MASIVO, json={
        "linea_ids": [l.id for l in lineas], "codigo": CODIGO,
        "opcion": OPCION_PRECIO_ENORME,
    })

    assert r.status_code == 422, r.text
    assert db.query(ConceptoAdicional).count() == 0
    for l in lineas:
        assert _total(db, l.id) == Decimal("0")
