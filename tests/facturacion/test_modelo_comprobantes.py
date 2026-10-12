"""El modelo de Comprobantes (facturacion/003), sobre SQLite en memoria.

Lo que se cuida acá es lo que el resto de la E2 da por hecho del modelo: las
Líneas se leen en su orden, la base hace cumplir la clave de identidad (de eso
depende el "sin duplicar" de la migración del histórico) y el nombre en disco
de cada adjunto, y borrar un Comprobante arrastra sus Líneas pero no sus
Adjuntos, que los borra el servicio junto con los archivos.

SQLite no hace cumplir las FK sin un PRAGMA: lo que se prueba del borrado es la
cascada de la relación, no la de la base. La de la base se ve en F1.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.facturacion.models import Adjunto, Comprobante, LineaComprobante


@pytest.fixture()
def fabrica():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def db(fabrica):
    sesion = fabrica()
    yield sesion
    sesion.close()


def comprobante(**campos):
    base = dict(
        tipo="factura", cliente_id=12, cliente_nombre="CLIENTE UNO",
        empresa_emisora="EMPRESA UNO", numero="A 0001", fecha=date(2026, 10, 5),
        clave_identidad="E|EMPRESA UNO|factura|A 0001",
    )
    return Comprobante(**{**base, **campos})


def linea(orden, **campos):
    base = dict(
        orden=orden, fecha=date(2026, 9, 16), tarea_id=7, tarea_nombre="TAREA A",
        unidad="plantas", cantidad=Decimal("10.00"),
        precio_unitario=Decimal("2.5000"), importe=Decimal("25.00"),
    )
    return LineaComprobante(**{**base, **campos})


def adjunto(nombre_en_disco, **campos):
    base = dict(
        nombre_original="factura.pdf", nombre_en_disco=nombre_en_disco,
        tipo_contenido="application/pdf", tamano_bytes=1234,
        subido_en=datetime(2026, 10, 12, 10, 0),
    )
    return Adjunto(**{**base, **campos})


def test_un_comprobante_con_dos_lineas_se_lee_en_el_orden_de_las_lineas(fabrica):
    db = fabrica()
    # Se agregan al revés a propósito: el orden lo da `orden`, no el id.
    c = comprobante(lineas=[linea(2, tarea_id=8), linea(1, tarea_id=7)])
    db.add(c)
    db.commit()
    id_ = c.id
    db.close()

    otra = fabrica()
    leido = otra.get(Comprobante, id_)
    assert [(l.orden, l.tarea_id) for l in leido.lineas] == [(1, 7), (2, 8)]
    # Los valores por defecto de la cabecera.
    assert leido.es_historico is False
    assert leido.pendiente_de_facturar is False
    assert leido.creado_en is not None
    assert leido.actualizado_en is None
    otra.close()


def test_una_clave_identidad_repetida_da_integrity_error(db):
    db.add(comprobante())
    db.commit()

    # Otro Cliente, misma clave: la base la rechaza igual.
    db.add(comprobante(cliente_id=13, cliente_nombre="CLIENTE DOS"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_un_historico_sin_numero_ni_empresa_ni_fecha_se_guarda(db):
    # Vacío sólo en un histórico sin número: la clave es la `S`.
    db.add(comprobante(
        empresa_emisora=None, numero=None, fecha=None, es_historico=True,
        pendiente_de_facturar=True, clave_identidad="S|12|2026-08-16",
    ))
    db.commit()

    guardado = db.query(Comprobante).one()
    assert guardado.numero is None
    assert guardado.pendiente_de_facturar is True


def test_borrar_el_comprobante_borra_sus_lineas(db):
    c = comprobante(lineas=[linea(1), linea(2)])
    db.add(c)
    db.commit()

    db.delete(c)
    db.commit()

    assert db.query(Comprobante).count() == 0
    assert db.query(LineaComprobante).count() == 0


def test_borrar_el_comprobante_no_arrastra_sus_adjuntos(db):
    # Sin cascada: los adjuntos los borra el servicio, que borra también los
    # archivos. Con un adjunto, el borrado directo falla.
    c = comprobante(adjuntos=[adjunto("a" * 32 + ".pdf")])
    db.add(c)
    db.commit()

    db.delete(c)
    with pytest.raises(IntegrityError):
        db.commit()


def test_un_nombre_en_disco_repetido_da_integrity_error(db):
    c = comprobante()
    db.add(c)
    db.commit()

    db.add(adjunto("b" * 32 + ".pdf", comprobante_id=c.id))
    db.commit()
    db.add(adjunto("b" * 32 + ".pdf", comprobante_id=c.id, nombre_original="otro.pdf"))
    with pytest.raises(IntegrityError):
        db.commit()
