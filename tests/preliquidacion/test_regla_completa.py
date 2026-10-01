"""Una regla del maestro (concepto_liquidacion) no se guarda sin código, sin
precio ni con precio <= 0 (ADR-0016). El 422 sale del schema con un texto en
español: "no vino" y "vino null" dan el mismo mensaje."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.auth import get_usuario_actual
from app.core.database import Base, get_db_propia
from app.modulos.preliquidacion.api.precios import actualizar_concepto, copiar_quincena
from app.modulos.preliquidacion.models import (
    ConceptoLiquidacion, TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.schemas import (
    ConceptoPrecioMasivoRequest, ConceptoUnifRequest, ConceptoUnifUpdateRequest,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _alta(**cambios):
    datos = {
        "quincena": date(2026, 9, 1),
        "tarea_nombre": "COSECHA",
        "codigo": 1,
        "precio": "100",
    }
    datos.update(cambios)
    return datos


def _sin(campo):
    datos = _alta()
    del datos[campo]
    return datos


# ─── Alta (ConceptoUnifRequest) ──────────────────────────────────────────────

def test_alta_sin_codigo_rechaza():
    with pytest.raises(ValidationError, match="Ingresá el código del concepto"):
        ConceptoUnifRequest(**_sin("codigo"))


def test_alta_codigo_null_explicito_rechaza():
    with pytest.raises(ValidationError, match="Ingresá el código del concepto"):
        ConceptoUnifRequest(**_alta(codigo=None))


def test_alta_sin_precio_rechaza():
    with pytest.raises(ValidationError, match="Ingresá el precio del concepto"):
        ConceptoUnifRequest(**_sin("precio"))


def test_alta_precio_cero_rechaza():
    with pytest.raises(ValidationError, match="El precio tiene que ser mayor que 0"):
        ConceptoUnifRequest(**_alta(precio="0"))


def test_alta_precio_negativo_rechaza():
    with pytest.raises(ValidationError, match="El precio tiene que ser mayor que 0"):
        ConceptoUnifRequest(**_alta(precio="-5"))


def test_alta_completa_pasa():
    obj = ConceptoUnifRequest(**_alta(codigo=1, precio="0.01"))
    assert obj.codigo == 1
    assert obj.precio == Decimal("0.01")


# ─── Edición parcial (ConceptoUnifUpdateRequest) ─────────────────────────────
# Omitir un campo no lo valida (el PATCH sigue siendo parcial); mandarlo null
# o con precio <= 0 sí rechaza. categoria y supervisor_nombre siguen admitiendo
# null explícito, que limpia el valor.

def test_update_codigo_null_explicito_rechaza():
    with pytest.raises(ValidationError, match="Ingresá el código del concepto"):
        ConceptoUnifUpdateRequest(codigo=None)


def test_update_precio_null_explicito_rechaza():
    with pytest.raises(ValidationError, match="Ingresá el precio del concepto"):
        ConceptoUnifUpdateRequest(precio=None)


def test_update_precio_cero_rechaza():
    with pytest.raises(ValidationError, match="El precio tiene que ser mayor que 0"):
        ConceptoUnifUpdateRequest(precio="0")


def test_update_omitir_codigo_y_precio_es_valido():
    obj = ConceptoUnifUpdateRequest(tipo=TipoConcepto.REMUNERATIVO)
    assert obj.model_dump(exclude_unset=True) == {"tipo": TipoConcepto.REMUNERATIVO}


def test_update_categoria_null_explicito_sigue_limpiando():
    obj = ConceptoUnifUpdateRequest(categoria=None)
    assert obj.model_dump(exclude_unset=True) == {"categoria": None}


def test_update_supervisor_nombre_null_explicito_sigue_limpiando():
    obj = ConceptoUnifUpdateRequest(supervisor_nombre=None)
    assert obj.model_dump(exclude_unset=True) == {"supervisor_nombre": None}


def test_patch_solo_precio_no_toca_codigo(db):
    concepto = ConceptoLiquidacion(
        quincena=date(2026, 5, 16), tarea_nombre="TAREA X",
        cliente_nombre="CLIENTE A", finca_nombre="FINCA 1",
        codigo=10, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("50"),
        tipo=TipoConcepto.OTRO, heredado=True,
    )
    db.add(concepto)
    db.commit()
    db.refresh(concepto)

    actualizar_concepto(
        concepto_id=concepto.id,
        datos=ConceptoUnifUpdateRequest(precio=Decimal("75")),
        db=db,
    )

    db.refresh(concepto)
    assert concepto.codigo == 10
    assert concepto.precio == Decimal("75")
    assert concepto.heredado is False


# ─── Precio masivo (ConceptoPrecioMasivoRequest) ─────────────────────────────

def test_precio_masivo_cero_rechaza():
    with pytest.raises(ValidationError, match="El precio tiene que ser mayor que 0"):
        ConceptoPrecioMasivoRequest(ids=[1], precio="0")


def test_precio_masivo_negativo_rechaza():
    with pytest.raises(ValidationError, match="El precio tiene que ser mayor que 0"):
        ConceptoPrecioMasivoRequest(ids=[1], precio="-10")


def test_precio_masivo_positivo_pasa():
    obj = ConceptoPrecioMasivoRequest(ids=[1], precio="0.01")
    assert obj.precio == Decimal("0.01")


# ─── Copia entre quincenas (copiar_quincena) ─────────────────────────────────
# Las reglas se crean por ORM: así pueden existir incompletas, como las viejas
# que quedaron en la base antes de ADR-0016.

QUINCENA_ORIGEN = date(2026, 5, 1)
QUINCENA_DESTINO = date(2026, 5, 16)


def _regla(db, quincena, tarea, codigo=1, precio=Decimal("100"), heredado=False):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea,
        cliente_nombre="CLIENTE A", finca_nombre="FINCA 1",
        codigo=codigo, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=precio,
        tipo=TipoConcepto.OTRO, heredado=heredado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _destino(db):
    return db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == QUINCENA_DESTINO
    ).all()


def _copiar(db):
    return copiar_quincena(
        quincena_origen=QUINCENA_ORIGEN, quincena_destino=QUINCENA_DESTINO, db=db,
    )


def test_copiar_omite_incompletas_e_informa(db):
    _regla(db, QUINCENA_ORIGEN, "TAREA A", codigo=10, precio=Decimal("50"))
    _regla(db, QUINCENA_ORIGEN, "TAREA B", codigo=20, precio=None)
    _regla(db, QUINCENA_ORIGEN, "TAREA C", codigo=None, precio=Decimal("50"))
    _regla(db, QUINCENA_ORIGEN, "TAREA D", codigo=40, precio=Decimal("0"))

    resultado = _copiar(db)

    destino = _destino(db)
    assert [c.tarea_nombre for c in destino] == ["TAREA A"]
    assert destino[0].heredado is True
    assert resultado.detalle == "1 copiados · 0 ya existían · 3 omitidas por incompletas"


def test_copiar_sin_incompletas_no_agrega_el_tramo(db):
    _regla(db, QUINCENA_ORIGEN, "TAREA A", codigo=10, precio=Decimal("50"))

    resultado = _copiar(db)

    assert resultado.detalle == "1 copiados · 0 ya existían"


def test_copiar_incompleta_que_ya_existe_en_destino_cuenta_como_incompleta(db):
    _regla(db, QUINCENA_ORIGEN, "TAREA B", codigo=20, precio=None)
    # Misma clave (tarea, cliente, finca, código, categoría, supervisor) en el destino.
    _regla(db, QUINCENA_DESTINO, "TAREA B", codigo=20, precio=Decimal("80"))

    resultado = _copiar(db)

    assert resultado.detalle == "0 copiados · 0 ya existían · 1 omitida por incompleta"
    destino = _destino(db)
    assert len(destino) == 1
    assert destino[0].precio == Decimal("80")


def test_copiar_una_incompleta_singular(db):
    _regla(db, QUINCENA_ORIGEN, "TAREA A", codigo=10, precio=Decimal("50"))
    _regla(db, QUINCENA_ORIGEN, "TAREA B", codigo=20, precio=None)

    resultado = _copiar(db)

    assert resultado.detalle == "1 copiados · 0 ya existían · 1 omitida por incompleta"


def test_copiar_todas_incompletas_responde_200_con_cero_copiados(db):
    _regla(db, QUINCENA_ORIGEN, "TAREA B", codigo=20, precio=None)
    _regla(db, QUINCENA_ORIGEN, "TAREA C", codigo=None, precio=Decimal("50"))

    resultado = _copiar(db)

    assert resultado.mensaje == "Conceptos copiados"
    assert resultado.detalle == "0 copiados · 0 ya existían · 2 omitidas por incompletas"
    assert _destino(db) == []


def test_copiar_origen_vacio_sigue_404(db):
    with pytest.raises(HTTPException) as exc:
        _copiar(db)
    assert exc.value.status_code == 404


# ─── El 422 por HTTP (caracterización) ───────────────────────────────────────
# Fija que el texto en español llega al cuerpo del 422 tal como lo muestra el
# front (mensajeError.js), y que el null de categoria sigue pasando el schema.

@pytest.fixture()
def cliente():
    # StaticPool + check_same_thread=False: el TestClient ejecuta el endpoint
    # en otro hilo y la base en memoria tiene que ser la misma conexión.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    admin = SimpleNamespace(id=1, rol="admin", modulos=[])
    app.dependency_overrides[get_usuario_actual] = lambda: admin
    app.dependency_overrides[get_db_propia] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()


def test_post_sin_codigo_ni_precio_da_422_en_espanol(cliente):
    r = cliente.post("/api/precios/conceptos", json={
        "quincena": "2026-09-01", "tarea_nombre": "COSECHA",
        "codigo": None, "precio": None,
    })
    assert r.status_code == 422, r.text
    assert "Ingresá el código del concepto" in r.text
    assert "Ingresá el precio del concepto" in r.text


def test_patch_precio_cero_da_422(cliente):
    r = cliente.patch("/api/precios/conceptos/1", json={"precio": 0})
    assert r.status_code == 422, r.text
    assert "El precio tiene que ser mayor que 0" in r.text


def test_patch_categoria_null_no_es_422_de_schema(cliente):
    # La base está vacía: si el schema deja pasar el null, el endpoint corre y
    # contesta 404. Un 422 querría decir que el schema lo rechazó.
    r = cliente.patch("/api/precios/conceptos/1", json={"categoria": None})
    assert r.status_code == 404, r.text
    assert "Concepto no encontrado" in r.text


def test_precio_masivo_cero_da_422(cliente):
    r = cliente.patch("/api/precios/conceptos/precio-masivo", json={"ids": [1], "precio": 0})
    assert r.status_code == 422, r.text
    assert "El precio tiene que ser mayor que 0" in r.text
