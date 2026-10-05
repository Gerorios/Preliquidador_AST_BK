"""ADR-0018: un Concepto no se repite.

Dos reglas con la misma quincena + tarea + cliente + finca + supervisor +
código + categoría son el mismo Concepto. El precio no participa; los textos
se comparan con TRIM y sin mayúsculas, y vacío cuenta igual que NULL. Lo
garantiza el índice único funcional `uq_concepto_unif`.

Sin base real (SQLite en memoria). Todos los datos son ficticios.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.auth import get_usuario_actual
from app.core.database import Base, get_db_propia
from app.modulos.preliquidacion.api.precios import (
    actualizar_concepto, copiar_quincena, crear_concepto,
)
from app.modulos.preliquidacion.models import (
    ConceptoLiquidacion, TipoConcepto, UnidadBaseConcepto,
)
from app.modulos.preliquidacion.schemas import (
    ConceptoUnifRequest, ConceptoUnifUpdateRequest,
)

Q1 = date(2026, 5, 1)
Q2 = date(2026, 5, 16)
TEXTO_461 = ("Ya existe una regla para esta tarea con el código 461. "
             "Si querés cambiar el precio, editá la existente.")


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _concepto(db, quincena=Q1, tarea="TAREA X", cliente=None, finca=None,
              supervisor=None, codigo=461, categoria=None, precio=Decimal("1000.00")):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente,
        finca_nombre=finca, supervisor_nombre=supervisor, codigo=codigo,
        categoria=categoria, unidad_base=UnidadBaseConcepto.HSJORNAL,
        precio=precio, tipo=TipoConcepto.REMUNERATIVO,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _rechaza(db, **kwargs):
    """Intenta cargar la regla y exige que el índice la rechace."""
    with pytest.raises(IntegrityError) as exc:
        _concepto(db, **kwargs)
    assert "uq_concepto_unif" in str(exc.value.orig)
    db.rollback()


# ─── Índice único ─────────────────────────────────────────────────────────────

def test_indice_rechaza_dos_reglas_iguales(db):
    """Iguales salvo el precio: es la misma regla y la base la rechaza."""
    _concepto(db, cliente="CLIENTE A", finca="FINCA A", precio=Decimal("1000.00"))
    _rechaza(db, cliente="CLIENTE A", finca="FINCA A", precio=Decimal("2500.00"))
    assert db.query(ConceptoLiquidacion).count() == 1


def test_indice_normaliza_espacios_y_mayusculas(db):
    _concepto(db, tarea="TAREA X", cliente="CLIENTE A", finca="FINCA A")
    _rechaza(db, tarea="  tarea x ", cliente="cliente a ", finca=" Finca A")
    _concepto(db, tarea="TAREA X", supervisor="PEREZ")
    _rechaza(db, tarea="Tarea X", supervisor=" perez ")
    assert db.query(ConceptoLiquidacion).count() == 2


def test_indice_trata_vacio_como_nulo(db):
    """Cliente, finca y supervisor vacíos cuentan igual que sin cargar."""
    _concepto(db)
    _rechaza(db, cliente="", finca="", supervisor="")
    _rechaza(db, supervisor="   ")
    _concepto(db, cliente="CLIENTE A", finca=None)
    _rechaza(db, cliente="CLIENTE A", finca="")
    assert db.query(ConceptoLiquidacion).count() == 2


def test_indice_permite_lo_legitimo(db):
    """Verde de control: el mismo código en reglas distintas sigue entrando."""
    _concepto(db)
    _concepto(db, tarea="TAREA Y")
    _concepto(db, cliente="CLIENTE A", finca="FINCA A")
    _concepto(db, cliente="CLIENTE A", finca="FINCA B")
    _concepto(db, categoria=3)
    _concepto(db, categoria=4)
    _concepto(db, quincena=Q2)
    _concepto(db, cliente="PEREZ")
    _concepto(db, supervisor="PEREZ")
    _concepto(db, codigo=462)
    assert db.query(ConceptoLiquidacion).count() == 10


# ─── Alta: el duplicado es un 409 con texto ──────────────────────────────────
# El detail es un string (no un dict como el del solapamiento): el front lo
# muestra tal cual en el toast.

def _req(**kwargs):
    base = dict(quincena=Q1, tarea_nombre="TAREA X", codigo=461,
                unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("1000.00"))
    base.update(kwargs)
    return ConceptoUnifRequest(**base)


def test_crear_dos_veces_la_misma_regla_da_409_con_texto(db):
    crear_concepto(datos=_req(), db=db)

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(precio=Decimal("2500.00")), db=db)

    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, str)
    assert exc.value.detail == TEXTO_461
    # La transacción fallida se descartó: la sesión sigue usable.
    assert db.query(ConceptoLiquidacion).count() == 1


def test_crear_con_otra_grafia_da_409(db):
    crear_concepto(datos=_req(supervisor_nombre="PEREZ"), db=db)

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(tarea_nombre="  tarea x ", supervisor_nombre=" perez "), db=db)

    assert exc.value.status_code == 409
    assert exc.value.detail == TEXTO_461
    assert db.query(ConceptoLiquidacion).count() == 1


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


def test_409_duplicado_por_http_tiene_detail_string(cliente):
    cuerpo = {
        "quincena": "2026-05-01", "tarea_nombre": "TAREA X", "codigo": 461,
        "precio": "1000", "confirmar_solapamiento": True,
    }
    assert cliente.post("/api/precios/conceptos", json=cuerpo).status_code == 200

    r = cliente.post("/api/precios/conceptos", json=cuerpo)

    assert r.status_code == 409, r.text
    assert r.json()["detail"] == TEXTO_461


# ─── Edición: el duplicado es un 409 y la fila no cambia ─────────────────────
# Por PATCH la clave cambia sólo vía código, categoría o supervisor.

def _editar_choca(db, concepto, **cambios):
    with pytest.raises(HTTPException) as exc:
        actualizar_concepto(concepto.id, ConceptoUnifUpdateRequest(**cambios), db=db)
    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, str)
    db.refresh(concepto)
    return exc.value.detail


def test_editar_codigo_que_choca_da_409_y_no_guarda(db):
    _concepto(db, codigo=461)
    otro = _concepto(db, codigo=462)

    detail = _editar_choca(db, otro, codigo=461)

    # El texto nombra el código intentado, no el que la fila conserva.
    assert detail == TEXTO_461
    assert otro.codigo == 462
    assert db.query(ConceptoLiquidacion).count() == 2


def test_editar_categoria_que_choca_da_409(db):
    _concepto(db, categoria=3)
    otro = _concepto(db, categoria=4)

    assert _editar_choca(db, otro, categoria=3) == TEXTO_461
    assert otro.categoria == 4


def test_editar_supervisor_que_choca_da_409(db):
    _concepto(db, supervisor="PEREZ")
    otro = _concepto(db, supervisor="GOMEZ")

    assert _editar_choca(db, otro, supervisor_nombre=" perez ") == TEXTO_461
    assert otro.supervisor_nombre == "GOMEZ"


def test_editar_la_misma_regla_sin_cambiar_clave_sigue_andando(db):
    """Verde de control: cambiar el precio no choca consigo misma."""
    c = _concepto(db, precio=Decimal("1000.00"))

    actualizar_concepto(c.id, ConceptoUnifUpdateRequest(precio=Decimal("2500.00")), db=db)

    db.refresh(c)
    assert c.precio == Decimal("2500.00")
    assert db.query(ConceptoLiquidacion).count() == 1


# ─── Copia entre quincenas: saltea con la misma clave ───────────────────────
# La copia compara además sin acentos, como la collation de MySQL: así nunca
# intenta insertar algo que el índice de producción rechazaría.

def _copiar(db):
    return copiar_quincena(quincena_origen=Q1, quincena_destino=Q2, db=db)


def _en_destino(db):
    return db.query(ConceptoLiquidacion).filter(ConceptoLiquidacion.quincena == Q2).all()


def test_copiar_saltea_la_que_existe_con_otra_grafia(db):
    _concepto(db, quincena=Q1, tarea="TAREA X", cliente="CLIENTE A", finca="FINCA A")
    _concepto(db, quincena=Q2, tarea=" tarea x ", cliente="cliente a ", finca=" Finca A")

    resultado = _copiar(db)

    assert resultado.detalle == "0 copiados · 1 ya existían"
    assert len(_en_destino(db)) == 1


def test_copiar_trata_finca_vacia_como_nula(db):
    _concepto(db, quincena=Q1, cliente="CLIENTE A", finca="")
    _concepto(db, quincena=Q2, cliente="CLIENTE A", finca=None)

    resultado = _copiar(db)

    assert resultado.detalle == "0 copiados · 1 ya existían"
    assert len(_en_destino(db)) == 1


def test_copiar_saltea_repetidas_dentro_del_origen(db):
    """SQLite no iguala acentos y deja convivir las dos en el origen; MySQL sí
    las iguala, así que la copia lleva una sola y la otra cuenta como existente."""
    _concepto(db, quincena=Q1, cliente="CLIENTE A", finca="FINCA TIMBO")
    _concepto(db, quincena=Q1, cliente="CLIENTE A", finca="FINCA TIMBÓ")

    resultado = _copiar(db)

    assert resultado.detalle == "1 copiados · 1 ya existían"
    assert len(_en_destino(db)) == 1


def test_copiar_dos_veces_a_la_vez_da_409_y_no_copia(db):
    """Doble clic en Copiar: los dos pedidos leen el destino antes de que
    alguno guarde y el segundo choca con el índice al hacer commit. Se simula
    ese choque: 409 con texto y el destino queda como estaba."""
    _concepto(db, quincena=Q1)

    def _commit_que_choca():
        raise IntegrityError(
            "INSERT INTO concepto_liquidacion (quincena, tarea_nombre) VALUES (?, ?)",
            ("2026-05-16", "TAREA X"),
            Exception("UNIQUE constraint failed: index 'uq_concepto_unif'"),
        )

    db.commit = _commit_que_choca

    with pytest.raises(HTTPException) as exc:
        _copiar(db)

    assert exc.value.status_code == 409
    assert exc.value.detail == ("Otra copia de esta quincena se hizo al mismo tiempo. "
                                "Recargá la página para ver el resultado.")
    assert _en_destino(db) == []
