"""El alta de Comprobantes (plan de la E2, sección 3.1, reglas 1 a 6), sobre
SQLite en memoria y con una consulta del campo falsa.

Lo que se cuida acá: lo que se guarda son copias del maestro y el importe lo
calcula el backend; la clave `E` hace que un número repetido con otra
escritura sea el mismo Comprobante; un número que ya tiene un histórico del
mismo Cliente se frena para no contar dos veces mientras la planilla siga
viva; y cada error dice qué campo (y qué fila, desde 1) lo causó, que es lo
que la pantalla necesita para marcarlo.

Datos inventados.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.facturacion.models import Adjunto, Comprobante, LineaComprobante
from app.modulos.facturacion.schemas import ComprobanteEntrada
from app.modulos.facturacion.services.comprobantes_service import (
    ComprobanteInvalido, ComprobanteModificado, ComprobanteNoEncontrado,
    ComprobanteRepetido, ComprobantesService, FacturaConNotas,
    HistoricoMismoNumero, HistoricoNoEditable, LineaInvalida,
)
from app.modulos.facturacion.services.reglas_comprobante import total_firmado

USUARIO = 5


class ConsultaFalsa:
    """Dos clientes (el 2 de baja), tres tareas (la 30 No facturable) y las
    fincas de cada cliente. Cuenta las lecturas, para ver que no se pide lo
    que no hace falta."""

    CLIENTES = [
        {"id": 1, "nombre": "CLIENTE UNO", "activo": True},
        {"id": 2, "nombre": "CLIENTE DOS", "activo": False},
    ]
    TAREAS = [
        {"tarea_id": 10, "nombre": "TAREA A", "grupo_tarea": "GRUPO A",
         "unidad_sugerida": "plantas", "no_facturable": False},
        {"tarea_id": 20, "nombre": "TAREA B", "grupo_tarea": "GRUPO B",
         "unidad_sugerida": "horas_peon", "no_facturable": False},
        {"tarea_id": 30, "nombre": "TAREA C", "grupo_tarea": "GRUPO C",
         "unidad_sugerida": None, "no_facturable": True},
    ]
    FINCAS = {
        1: [{"id": 100, "nombre": "FINCA UNO"}],
        2: [{"id": 200, "nombre": "FINCA DOS"}],
    }

    def __init__(self):
        self.lecturas_de_fincas = []

    def clientes(self, incluir_baja=False):
        return [c for c in self.CLIENTES if incluir_baja or c["activo"]]

    def obtener_tareas(self, incluir_baja=False):
        return list(self.TAREAS)

    def fincas_de_cliente(self, cliente_id):
        self.lecturas_de_fincas.append(cliente_id)
        return list(self.FINCAS.get(cliente_id, []))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    yield sesion
    sesion.close()
    engine.dispose()


@pytest.fixture()
def consulta():
    return ConsultaFalsa()


@pytest.fixture()
def servicio(db, consulta):
    return ComprobantesService(db, consulta)


def linea(**campos):
    base = {"fecha": "2026-09-16", "tarea_id": 10, "unidad": "plantas",
            "finca_id": None, "cantidad": "1234.50", "precio_unitario": "98.1234"}
    return {**base, **campos}


def entrada(**campos):
    base = {"tipo": "factura", "cliente_id": 1, "empresa_emisora": "EMPRESA UNO",
            "numero": "A 0001", "fecha": "2026-10-05", "factura_corregida_id": None,
            "lineas": [linea()]}
    return ComprobanteEntrada(**{**base, **campos})


def historico(db, **campos):
    """Un histórico como lo deja la migración: sin Empresa y con clave `H`."""
    base = dict(
        tipo="factura", cliente_id=1, cliente_nombre="CLIENTE UNO",
        empresa_emisora=None, numero="B 0007", fecha=date(2025, 8, 1),
        es_historico=True, clave_identidad="H|1|B 0007",
        lineas=[LineaComprobante(
            orden=1, fecha=date(2025, 8, 1), tarea_id=10, tarea_nombre="TAREA A",
            unidad="plantas", cantidad=Decimal("1.00"),
            precio_unitario=Decimal("10.0000"), importe=Decimal("10.00"))],
    )
    c = Comprobante(**{**base, **campos})
    db.add(c)
    db.commit()
    return c


# ─── Excepciones ────────────────────────────────────────────────────────────

def test_las_excepciones_llevan_lo_que_el_router_necesita():
    assert ComprobanteRepetido(7).comprobante_id == 7
    assert HistoricoMismoNumero(8).comprobante_id == 8
    invalido = ComprobanteInvalido("numero", "mensaje")
    assert (invalido.campo, invalido.mensaje) == ("numero", "mensaje")
    linea_mala = LineaInvalida(2, "tarea_id", "mensaje")
    assert (linea_mala.fila, linea_mala.campo) == (2, "tarea_id")
    # Las de la edición y el borrado (A5) existen desde ya, con su mensaje.
    for excepcion in (ComprobanteNoEncontrado(), HistoricoNoEditable(), FacturaConNotas()):
        assert excepcion.mensaje


# ─── Alta ───────────────────────────────────────────────────────────────────

def test_el_alta_guarda_copias_del_maestro_el_importe_calculado_y_la_clave_e(
        servicio, db, consulta):
    c = servicio.crear(entrada(
        empresa_emisora="  empresa uno ", numero="  a   0001 ",
        lineas=[linea(),
                linea(tarea_id=20, unidad="horas_peon", finca_id=100,
                      cantidad=3, precio_unitario="0.005")],
    ), usuario_id=USUARIO)

    db.expire_all()
    guardado = db.get(Comprobante, c.id)
    assert guardado.tipo == "factura"
    assert guardado.cliente_id == 1
    assert guardado.cliente_nombre == "CLIENTE UNO"
    assert guardado.empresa_emisora == "EMPRESA UNO"
    assert guardado.numero == "A 0001"
    assert guardado.fecha == date(2026, 10, 5)
    assert guardado.clave_identidad == "E|EMPRESA UNO|factura|A 0001"
    assert guardado.es_historico is False
    assert guardado.factura_corregida_id is None
    assert guardado.creado_por == USUARIO
    assert guardado.creado_en is not None
    assert guardado.actualizado_en is None

    primera, segunda = guardado.lineas
    assert (primera.orden, primera.tarea_id, primera.tarea_nombre) == (1, 10, "TAREA A")
    assert primera.fecha == date(2026, 9, 16)
    assert (primera.finca_id, primera.finca_nombre) == (None, None)
    assert primera.cantidad == Decimal("1234.50")
    assert primera.precio_unitario == Decimal("98.1234")
    # 1234.50 × 98.1234 = 121133.3373 → 121133.34
    assert primera.importe == Decimal("121133.34")
    assert (segunda.orden, segunda.tarea_nombre, segunda.unidad) == (2, "TAREA B", "horas_peon")
    assert (segunda.finca_id, segunda.finca_nombre) == (100, "FINCA UNO")
    # El caso fijo de A1 que el front repite: 3 × 0.005 = 0.015 → 0.02.
    assert segunda.importe == Decimal("0.02")
    # Las fincas se leen del Cliente del Comprobante, una sola vez.
    assert consulta.lecturas_de_fincas == [1]


def test_los_decimales_entran_como_numero_o_como_texto():
    e = entrada(lineas=[linea(cantidad=1234.5, precio_unitario="98.1234")])
    assert e.lineas[0].cantidad == Decimal("1234.5")
    assert e.lineas[0].precio_unitario == Decimal("98.1234")


def test_sin_fincas_no_se_lee_la_base_de_campo(servicio, consulta):
    servicio.crear(entrada(), usuario_id=USUARIO)
    assert consulta.lecturas_de_fincas == []


def test_una_tarea_no_facturable_se_acepta(servicio):
    c = servicio.crear(entrada(lineas=[linea(tarea_id=30, unidad="bins")]),
                       usuario_id=USUARIO)
    assert c.lineas[0].tarea_nombre == "TAREA C"


# ─── Repetidos ──────────────────────────────────────────────────────────────

def test_el_mismo_numero_con_otra_escritura_es_repetido(servicio, db):
    primero = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.crear(entrada(empresa_emisora="empresa uno  ",
                               numero=" a  0001"), usuario_id=USUARIO)
    assert error.value.comprobante_id == primero.id
    assert db.query(Comprobante).count() == 1


def test_el_mismo_numero_en_otra_empresa_no_es_repetido(servicio, db):
    servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.crear(entrada(empresa_emisora="EMPRESA DOS"), usuario_id=USUARIO)
    assert db.query(Comprobante).count() == 2


def test_si_el_repetido_lo_frena_la_base_tambien_es_repetido(servicio, db, monkeypatch):
    # Dos personas cargando el mismo a la vez (pregunta 18): las dos pasan el
    # control previo y la base frena a la segunda con el UNIQUE de la clave.
    # Tiene que llegar como 409 con el id, no como 500.
    primero = servicio.crear(entrada(), usuario_id=USUARIO)
    real = servicio._por_clave
    llamadas = []

    def control_previo_ciego(clave):
        # La primera búsqueda es el control previo, que no lo ve; la que hace
        # el servicio después del choque con la base sí.
        llamadas.append(clave)
        return None if len(llamadas) == 1 else real(clave)

    monkeypatch.setattr(servicio, "_por_clave", control_previo_ciego)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.crear(entrada(), usuario_id=USUARIO)
    assert len(llamadas) == 2
    assert error.value.comprobante_id == primero.id
    assert db.query(Comprobante).count() == 1


def test_un_numero_que_ya_tiene_un_historico_del_cliente_se_frena(servicio, db):
    viejo = historico(db)

    with pytest.raises(HistoricoMismoNumero) as error:
        servicio.crear(entrada(numero=" b 0007 "), usuario_id=USUARIO)
    assert error.value.comprobante_id == viejo.id
    assert db.query(Comprobante).count() == 1


def test_el_numero_de_un_historico_de_otro_cliente_no_frena(servicio, db):
    historico(db, cliente_id=99, cliente_nombre="CLIENTE NUEVE",
              clave_identidad="H|99|B 0007")
    servicio.crear(entrada(numero="B 0007"), usuario_id=USUARIO)
    assert db.query(Comprobante).count() == 2


# ─── Cabecera inválida ──────────────────────────────────────────────────────

@pytest.mark.parametrize("campos, campo", [
    ({"cliente_id": 2}, "cliente_id"),            # de baja
    ({"cliente_id": 99}, "cliente_id"),           # no existe
    ({"tipo": "nota_debito"}, "tipo"),
    ({"empresa_emisora": "   "}, "empresa_emisora"),
    ({"empresa_emisora": None}, "empresa_emisora"),
    ({"empresa_emisora": "E" * 101}, "empresa_emisora"),
    ({"numero": None}, "numero"),
    ({"numero": "   "}, "numero"),
    ({"numero": "A|1"}, "numero"),
    # 31 caracteres después de normalizar: no entra en la columna.
    ({"numero": "  " + "1" * 31 + "  "}, "numero"),
    ({"fecha": None}, "fecha"),
    ({"lineas": []}, "lineas"),
    # Una Factura no corrige a otra.
    ({"factura_corregida_id": 1}, "factura_corregida_id"),
])
def test_cabecera_invalida(servicio, db, campos, campo):
    with pytest.raises(ComprobanteInvalido) as error:
        servicio.crear(entrada(**campos), usuario_id=USUARIO)
    assert error.value.campo == campo
    assert error.value.mensaje
    assert db.query(Comprobante).count() == 0


def test_un_numero_de_30_caracteres_entra(servicio):
    c = servicio.crear(entrada(numero="1" * 30), usuario_id=USUARIO)
    assert c.numero == "1" * 30


# ─── Líneas inválidas ───────────────────────────────────────────────────────

@pytest.mark.parametrize("campos, campo", [
    ({"tarea_id": 999}, "tarea_id"),
    ({"unidad": "kilos"}, "unidad"),
    ({"unidad": "PLANTAS"}, "unidad"),
    ({"finca_id": 200}, "finca_id"),              # es del CLIENTE DOS
    ({"finca_id": 999}, "finca_id"),
    ({"cantidad": "0"}, "cantidad"),
    ({"cantidad": "-1"}, "cantidad"),
    ({"precio_unitario": "-0.01"}, "precio_unitario"),
    # Más decimales que los de la columna: la base los redondearía y el
    # importe quedaría calculado sobre otro número.
    ({"cantidad": "1.234"}, "cantidad"),
    ({"precio_unitario": "1.23456"}, "precio_unitario"),
    # Más dígitos de los que entran en la columna.
    ({"cantidad": "1" * 13}, "cantidad"),
    ({"precio_unitario": "1" * 11}, "precio_unitario"),
])
def test_linea_invalida_dice_la_fila_y_el_campo(servicio, db, campos, campo):
    with pytest.raises(LineaInvalida) as error:
        servicio.crear(entrada(lineas=[linea(), linea(**campos)]), usuario_id=USUARIO)
    assert (error.value.fila, error.value.campo) == (2, campo)
    assert error.value.mensaje
    assert db.query(Comprobante).count() == 0


def test_un_importe_que_no_entra_en_la_columna_es_linea_invalida(servicio):
    with pytest.raises(LineaInvalida) as error:
        servicio.crear(entrada(lineas=[linea(cantidad="999999999999",
                                             precio_unitario="10")]),
                       usuario_id=USUARIO)
    assert (error.value.fila, error.value.campo) == (1, "importe")


def test_precio_cero_se_acepta(servicio):
    c = servicio.crear(entrada(lineas=[linea(precio_unitario="0")]), usuario_id=USUARIO)
    assert c.lineas[0].importe == Decimal("0.00")


# ─── Nota de crédito ────────────────────────────────────────────────────────

def nota(factura_id, **campos):
    base = {"tipo": "nota_credito", "numero": "NC 0001",
            "factura_corregida_id": factura_id,
            "lineas": [linea(cantidad="2", precio_unitario="10")]}
    return entrada(**{**base, **campos})


def test_una_nota_de_credito_sin_factura_es_invalida(servicio, db):
    with pytest.raises(ComprobanteInvalido) as error:
        servicio.crear(nota(None), usuario_id=USUARIO)
    assert error.value.campo == "factura_corregida_id"
    assert db.query(Comprobante).count() == 0


def test_una_nota_de_credito_a_una_factura_que_no_existe_es_invalida(servicio):
    with pytest.raises(ComprobanteInvalido) as error:
        servicio.crear(nota(999), usuario_id=USUARIO)
    assert error.value.campo == "factura_corregida_id"


def test_una_nota_de_credito_no_corrige_otra_nota(servicio):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    primera = servicio.crear(nota(factura.id), usuario_id=USUARIO)

    with pytest.raises(ComprobanteInvalido) as error:
        servicio.crear(nota(primera.id, numero="NC 0002"), usuario_id=USUARIO)
    assert error.value.campo == "factura_corregida_id"


def test_una_nota_de_credito_no_corrige_la_factura_de_otro_cliente(servicio, db):
    ajena = historico(db, cliente_id=99, cliente_nombre="CLIENTE NUEVE",
                      clave_identidad="H|99|B 0007")

    with pytest.raises(ComprobanteInvalido) as error:
        servicio.crear(nota(ajena.id), usuario_id=USUARIO)
    assert error.value.campo == "factura_corregida_id"


def test_una_nota_de_credito_valida_corrige_un_historico_y_da_total_negativo(
        servicio, db):
    factura = historico(db)

    # Otra Empresa que la de la Factura (el histórico no tiene): no se valida.
    nc = servicio.crear(nota(factura.id, empresa_emisora="EMPRESA DOS"),
                        usuario_id=USUARIO)

    db.expire_all()
    guardada = db.get(Comprobante, nc.id)
    assert guardada.tipo == "nota_credito"
    assert guardada.factura_corregida_id == factura.id
    assert guardada.clave_identidad == "E|EMPRESA DOS|nota_credito|NC 0001"
    # El importe de la Línea se guarda positivo; el signo lo da el tipo.
    assert guardada.lineas[0].importe == Decimal("20.00")
    assert total_firmado(guardada.tipo, [l.importe for l in guardada.lineas]) == Decimal("-20.00")


def test_el_total_de_una_factura_es_positivo(servicio):
    c = servicio.crear(entrada(lineas=[linea(cantidad="2", precio_unitario="10"),
                                       linea(cantidad="1", precio_unitario="0.5")]),
                       usuario_id=USUARIO)
    assert total_firmado(c.tipo, [l.importe for l in c.lineas]) == Decimal("20.50")


# ═══ Edición, borrado, listado y detalle (A5; sección 3.1, regla 7) ═════════

OTRO_USUARIO = 6
TERCERO = {"id": 3, "nombre": "CLIENTE TRES", "activo": True}


@pytest.fixture()
def con_tercer_cliente(consulta):
    """Un segundo Cliente activo, para cambiar de Cliente al editar."""
    consulta.CLIENTES = ConsultaFalsa.CLIENTES + [TERCERO]
    return consulta


def dar_de_baja(consulta, cliente_id):
    """El Cliente pasa a baja en el maestro después de cargar el Comprobante."""
    consulta.CLIENTES = [{**c, "activo": False} if c["id"] == cliente_id else c
                         for c in consulta.CLIENTES]


def adjunto(db, comprobante, nombre="factura.pdf"):
    """Una fila de Adjunto, sin archivo: subirlos llega con BK-B."""
    a = Adjunto(comprobante_id=comprobante.id, nombre_original=nombre,
                nombre_en_disco=f"{comprobante.id}-{nombre}",
                tipo_contenido="application/pdf", tamano_bytes=1234)
    db.add(a)
    db.commit()
    return a


# ─── Edición ────────────────────────────────────────────────────────────────

def test_el_put_reemplaza_la_cabecera_y_todas_las_lineas_y_sella_quien_edito(
        servicio, db):
    c = servicio.crear(entrada(lineas=[linea(), linea(tarea_id=20, unidad="horas_peon")]),
                       usuario_id=USUARIO)

    servicio.editar(c.id, entrada(
        empresa_emisora=" empresa dos ", numero=" a  0002 ", fecha="2026-10-06",
        lineas=[linea(tarea_id=30, unidad="bins", cantidad="2", precio_unitario="10")],
    ), usuario_id=OTRO_USUARIO)

    db.expire_all()
    guardado = db.get(Comprobante, c.id)
    assert guardado.empresa_emisora == "EMPRESA DOS"
    assert guardado.numero == "A 0002"
    assert guardado.fecha == date(2026, 10, 6)
    # La clave se recalcula con la cabecera nueva.
    assert guardado.clave_identidad == "E|EMPRESA DOS|factura|A 0002"
    assert guardado.creado_por == USUARIO
    assert guardado.actualizado_por == OTRO_USUARIO
    assert guardado.actualizado_en is not None
    # Las Líneas viejas no quedan: el PUT reemplaza todas.
    assert db.query(LineaComprobante).count() == 1
    (unica,) = guardado.lineas
    assert (unica.orden, unica.tarea_nombre, unica.unidad) == (1, "TAREA C", "bins")
    assert unica.importe == Decimal("20.00")


def test_editar_sin_cambiar_el_numero_no_es_repetido_de_si_mismo(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.editar(c.id, entrada(numero=" a 0001 ", fecha="2026-10-07"),
                    usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, c.id).fecha == date(2026, 10, 7)


def test_editar_al_numero_de_otro_comprobante_es_repetido(servicio, db):
    otro = servicio.crear(entrada(numero="A 0002"), usuario_id=USUARIO)
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.editar(c.id, entrada(numero="a 0002"), usuario_id=OTRO_USUARIO)
    assert error.value.comprobante_id == otro.id
    db.expire_all()
    sin_tocar = db.get(Comprobante, c.id)
    assert sin_tocar.numero == "A 0001"
    assert sin_tocar.actualizado_en is None


def test_si_el_repetido_al_editar_lo_frena_la_base_tambien_es_repetido(
        servicio, db, monkeypatch):
    # Pregunta 18, ahora en la edición: el control previo no lo ve y la base sí.
    otro = servicio.crear(entrada(numero="A 0002"), usuario_id=USUARIO)
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    real = servicio._por_clave
    llamadas = []

    def control_previo_ciego(clave):
        llamadas.append(clave)
        return None if len(llamadas) == 1 else real(clave)

    monkeypatch.setattr(servicio, "_por_clave", control_previo_ciego)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.editar(c.id, entrada(numero="A 0002"), usuario_id=OTRO_USUARIO)
    assert len(llamadas) == 2
    assert error.value.comprobante_id == otro.id
    db.expire_all()
    assert db.get(Comprobante, c.id).numero == "A 0001"


def test_editar_al_numero_de_un_historico_del_cliente_se_frena(servicio, db):
    viejo = historico(db)
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(HistoricoMismoNumero) as error:
        servicio.editar(c.id, entrada(numero="b 0007"), usuario_id=USUARIO)
    assert error.value.comprobante_id == viejo.id


def test_editar_valida_igual_que_el_alta_y_no_toca_nada(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(LineaInvalida) as error:
        servicio.editar(c.id, entrada(lineas=[linea(), linea(unidad="kilos")]),
                        usuario_id=OTRO_USUARIO)
    assert (error.value.fila, error.value.campo) == (2, "unidad")
    with pytest.raises(ComprobanteInvalido) as error:
        servicio.editar(c.id, entrada(fecha=None), usuario_id=OTRO_USUARIO)
    assert error.value.campo == "fecha"

    db.expire_all()
    sin_tocar = db.get(Comprobante, c.id)
    assert sin_tocar.actualizado_en is None
    assert len(sin_tocar.lineas) == 1


def test_editar_uno_que_no_existe(servicio):
    with pytest.raises(ComprobanteNoEncontrado):
        servicio.editar(999, entrada(), usuario_id=USUARIO)


def test_un_historico_no_se_edita(servicio, db):
    viejo = historico(db)

    with pytest.raises(HistoricoNoEditable):
        servicio.editar(viejo.id, entrada(), usuario_id=USUARIO)
    db.expire_all()
    sin_tocar = db.get(Comprobante, viejo.id)
    assert sin_tocar.numero == "B 0007"
    assert sin_tocar.empresa_emisora is None
    assert sin_tocar.actualizado_en is None


def test_una_factura_con_notas_no_cambia_de_cliente(servicio, db, con_tercer_cliente):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.crear(nota(factura.id), usuario_id=USUARIO)

    with pytest.raises(FacturaConNotas):
        servicio.editar(factura.id, entrada(cliente_id=3), usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, factura.id).cliente_id == 1


def test_una_factura_con_notas_no_cambia_de_tipo(servicio, db):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    otra = servicio.crear(entrada(numero="A 0002"), usuario_id=USUARIO)
    servicio.crear(nota(factura.id), usuario_id=USUARIO)

    with pytest.raises(FacturaConNotas):
        servicio.editar(factura.id, nota(otra.id, numero="A 0001"), usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, factura.id).tipo == "factura"


def test_una_factura_con_notas_si_cambia_lo_demas(servicio, db):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.crear(nota(factura.id), usuario_id=USUARIO)

    servicio.editar(factura.id, entrada(numero="A 0009",
                                        lineas=[linea(cantidad="3", precio_unitario="1")]),
                    usuario_id=OTRO_USUARIO)
    db.expire_all()
    guardada = db.get(Comprobante, factura.id)
    assert guardada.numero == "A 0009"
    assert guardada.lineas[0].importe == Decimal("3.00")


def test_una_factura_sin_notas_cambia_de_cliente_y_copia_su_nombre(
        servicio, db, con_tercer_cliente):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)

    servicio.editar(factura.id, entrada(cliente_id=3), usuario_id=OTRO_USUARIO)
    db.expire_all()
    guardada = db.get(Comprobante, factura.id)
    assert (guardada.cliente_id, guardada.cliente_nombre) == (3, "CLIENTE TRES")


def test_conservar_un_cliente_que_paso_a_baja_se_permite(servicio, db, consulta):
    c = servicio.crear(entrada(lineas=[linea(finca_id=100)]), usuario_id=USUARIO)
    dar_de_baja(consulta, 1)

    servicio.editar(c.id, entrada(numero="A 0003", lineas=[linea(finca_id=100)]),
                    usuario_id=OTRO_USUARIO)
    db.expire_all()
    guardado = db.get(Comprobante, c.id)
    assert (guardado.cliente_id, guardado.cliente_nombre) == (1, "CLIENTE UNO")
    assert guardado.numero == "A 0003"
    assert guardado.lineas[0].finca_nombre == "FINCA UNO"


def test_pasar_a_un_cliente_de_baja_al_editar_no_se_permite(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(ComprobanteInvalido) as error:
        servicio.editar(c.id, entrada(cliente_id=2), usuario_id=OTRO_USUARIO)
    assert error.value.campo == "cliente_id"


def test_una_nota_de_credito_no_se_corrige_a_si_misma(servicio, db):
    # Una Factura sin notas que pasa a Nota de crédito no puede apuntarse a sí
    # misma: después del PUT ya no sería una Factura (regla 5).
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(ComprobanteInvalido) as error:
        servicio.editar(c.id, nota(c.id), usuario_id=OTRO_USUARIO)
    assert error.value.campo == "factura_corregida_id"


def test_una_nota_de_credito_se_edita_y_sigue_corrigiendo_su_factura(servicio, db):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    nc = servicio.crear(nota(factura.id), usuario_id=USUARIO)

    servicio.editar(nc.id, nota(factura.id, numero="NC 0005"), usuario_id=OTRO_USUARIO)
    db.expire_all()
    guardada = db.get(Comprobante, nc.id)
    assert guardada.numero == "NC 0005"
    assert guardada.factura_corregida_id == factura.id


# ─── Borrado ────────────────────────────────────────────────────────────────

def test_borrar_se_lleva_el_comprobante_y_sus_lineas(servicio, db):
    c = servicio.crear(entrada(lineas=[linea(), linea()]), usuario_id=USUARIO)
    queda = servicio.crear(entrada(numero="A 0002"), usuario_id=USUARIO)

    servicio.borrar(c.id)
    db.expire_all()
    assert db.get(Comprobante, c.id) is None
    assert db.query(LineaComprobante).count() == 1
    assert db.get(Comprobante, queda.id) is not None


def test_borrar_uno_que_no_existe(servicio):
    with pytest.raises(ComprobanteNoEncontrado):
        servicio.borrar(999)


def test_un_historico_no_se_borra(servicio, db):
    viejo = historico(db)

    with pytest.raises(HistoricoNoEditable):
        servicio.borrar(viejo.id)
    db.expire_all()
    assert db.get(Comprobante, viejo.id) is not None


def test_una_factura_con_notas_no_se_borra_y_su_nota_si(servicio, db):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    nc = servicio.crear(nota(factura.id), usuario_id=USUARIO)

    with pytest.raises(FacturaConNotas):
        servicio.borrar(factura.id)
    db.expire_all()
    assert db.get(Comprobante, factura.id) is not None

    servicio.borrar(nc.id)
    servicio.borrar(factura.id)
    db.expire_all()
    assert db.query(Comprobante).count() == 0


# ─── Listado ────────────────────────────────────────────────────────────────

CAMPOS_FILA = {
    "id", "tipo", "numero", "fecha", "mes", "cliente_id", "cliente_nombre",
    "empresa_emisora", "es_historico", "pendiente_de_facturar",
    "cantidad_lineas", "cantidad_adjuntos", "total_neto",
}


def test_listar_trae_signo_conteos_mes_y_orden(servicio, db):
    # Factura con dos Líneas: el mes es el de la primera (orden 1), no el de
    # la más vieja.
    factura = servicio.crear(entrada(lineas=[
        linea(fecha="2026-09-16", cantidad="2", precio_unitario="10"),
        linea(fecha="2026-08-01", cantidad="1", precio_unitario="0.5"),
    ]), usuario_id=USUARIO)
    adjunto(db, factura, "uno.pdf")
    adjunto(db, factura, "dos.pdf")
    nc = servicio.crear(nota(factura.id, fecha="2026-10-20"), usuario_id=USUARIO)
    # Histórico sin fecha de comprobante: se ordena por su primera Línea
    # (2026-10-10), entre la NC y la Factura.
    sin_fecha = historico(db, fecha=None, clave_identidad="H|1|B 0008", numero="B 0008",
                          lineas=[LineaComprobante(
                              orden=1, fecha=date(2026, 10, 10), tarea_id=10,
                              tarea_nombre="TAREA A", unidad="plantas",
                              cantidad=Decimal("1.00"), precio_unitario=Decimal("5.0000"),
                              importe=Decimal("5.00"))])
    # Histórico sin número, pendiente de facturar, el más viejo.
    sin_numero = historico(db, numero=None, pendiente_de_facturar=True,
                           clave_identidad="S|1|2025-08-01")

    filas = servicio.listar()

    assert [f["id"] for f in filas] == [nc.id, sin_fecha.id, factura.id, sin_numero.id]
    for f in filas:
        assert set(f) == CAMPOS_FILA
    f_nc, f_sin_fecha, f_factura, f_sin_numero = filas

    assert f_factura["total_neto"] == Decimal("20.50")
    assert f_factura["cantidad_lineas"] == 2
    assert f_factura["cantidad_adjuntos"] == 2
    assert f_factura["mes"] == "2026-09"
    assert f_factura["numero"] == "A 0001"
    assert f_factura["empresa_emisora"] == "EMPRESA UNO"
    assert f_factura["fecha"] == date(2026, 10, 5)
    assert (f_factura["es_historico"], f_factura["pendiente_de_facturar"]) == (False, False)

    assert f_nc["tipo"] == "nota_credito"
    assert f_nc["total_neto"] == Decimal("-20.00")
    assert f_nc["cantidad_adjuntos"] == 0

    assert f_sin_fecha["fecha"] is None
    assert f_sin_fecha["mes"] == "2026-10"
    assert f_sin_fecha["es_historico"] is True

    assert f_sin_numero["numero"] is None
    assert f_sin_numero["pendiente_de_facturar"] is True
    assert f_sin_numero["empresa_emisora"] is None
    assert f_sin_numero["total_neto"] == Decimal("10.00")
    assert f_sin_numero["cliente_nombre"] == "CLIENTE UNO"


def test_listar_sin_comprobantes(servicio):
    assert servicio.listar() == []


def test_listar_no_hace_una_consulta_por_comprobante(servicio, db):
    consultas = []
    motor = db.get_bind()

    def contar(*args, **kwargs):
        consultas.append(1)

    def consultas_de_listar():
        db.expire_all()
        consultas.clear()
        event.listen(motor, "before_cursor_execute", contar)
        try:
            servicio.listar()
        finally:
            event.remove(motor, "before_cursor_execute", contar)
        return len(consultas)

    c = servicio.crear(entrada(), usuario_id=USUARIO)
    adjunto(db, c)
    con_uno = consultas_de_listar()
    for n in range(2, 6):
        otro = servicio.crear(entrada(numero=f"A 000{n}"), usuario_id=USUARIO)
        adjunto(db, otro)
    con_cinco = consultas_de_listar()
    assert con_cinco == con_uno


# ─── Detalle ────────────────────────────────────────────────────────────────

def test_el_detalle_de_una_factura_trae_lineas_notas_y_adjuntos(servicio, db):
    factura = servicio.crear(entrada(lineas=[
        linea(finca_id=100, cantidad="2", precio_unitario="10"),
        linea(fecha="2026-10-01", tarea_id=20, unidad="horas_peon",
              cantidad="1", precio_unitario="0.5"),
    ]), usuario_id=USUARIO)
    a = adjunto(db, factura)
    nc1 = servicio.crear(nota(factura.id, fecha="2026-10-20"), usuario_id=USUARIO)
    nc2 = servicio.crear(nota(factura.id, numero="NC 0002", fecha="2026-10-21"),
                         usuario_id=USUARIO)

    d = servicio.detalle(factura.id)

    assert CAMPOS_FILA <= set(d)
    assert d["id"] == factura.id
    assert d["total_neto"] == Decimal("20.50")
    assert (d["cantidad_lineas"], d["cantidad_adjuntos"], d["mes"]) == (2, 1, "2026-09")
    assert d["factura_corregida"] is None
    assert d["notas_credito"] == [
        {"id": nc1.id, "numero": "NC 0001", "fecha": date(2026, 10, 20)},
        {"id": nc2.id, "numero": "NC 0002", "fecha": date(2026, 10, 21)},
    ]
    primera, segunda = d["lineas"]
    assert primera == {
        "id": primera["id"], "orden": 1, "fecha": date(2026, 9, 16),
        "tarea_id": 10, "tarea_nombre": "TAREA A", "unidad": "plantas",
        "finca_id": 100, "finca_nombre": "FINCA UNO",
        "cantidad": Decimal("2.00"), "precio_unitario": Decimal("10.0000"),
        "importe": Decimal("20.00"),
    }
    assert (segunda["orden"], segunda["tarea_nombre"], segunda["importe"]) == (
        2, "TAREA B", Decimal("0.50"))
    assert d["adjuntos"] == [{
        "id": a.id, "nombre_original": "factura.pdf",
        "tipo_contenido": "application/pdf", "tamano_bytes": 1234,
        "subido_en": a.subido_en,
    }]
    assert d["creado_en"] is not None
    assert d["actualizado_en"] is None


def test_el_detalle_de_una_nota_trae_su_factura_y_el_importe_positivo(servicio, db):
    factura = historico(db)
    nc = servicio.crear(nota(factura.id), usuario_id=USUARIO)
    servicio.editar(nc.id, nota(factura.id), usuario_id=OTRO_USUARIO)

    d = servicio.detalle(nc.id)

    assert d["factura_corregida"] == {"id": factura.id, "numero": "B 0007",
                                      "fecha": date(2025, 8, 1)}
    assert d["notas_credito"] == []
    assert d["total_neto"] == Decimal("-20.00")
    # La Línea va positiva: el signo lo pone el front según el tipo.
    assert d["lineas"][0]["importe"] == Decimal("20.00")
    assert d["actualizado_en"] is not None


def test_el_detalle_de_uno_que_no_existe(servicio):
    with pytest.raises(ComprobanteNoEncontrado):
        servicio.detalle(999)


# ═══ A5b: edición simultánea, tarea de baja y borrado frenado por la base ═══

# ─── Edición simultánea (pregunta 18) ───────────────────────────────────────

def test_comprobante_modificado_lleva_mensaje():
    assert ComprobanteModificado().mensaje


def test_el_sello_de_la_edicion_va_sin_microsegundos(servicio, db):
    # MySQL guarda DATETIME sin fracción (y la redondea): si el sello la
    # tuviera, el valor que devuelve el detalle no sería el que se guardó.
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.editar(c.id, entrada(), usuario_id=OTRO_USUARIO)
    db.expire_all()
    assert db.get(Comprobante, c.id).actualizado_en.microsecond == 0


def test_el_put_con_el_actualizado_en_del_detalle_pasa_y_el_viejo_no(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    # Nunca editado: null contra null.
    servicio.editar(c.id, entrada(numero="A 0002"), usuario_id=USUARIO)
    leido = servicio.detalle(c.id)["actualizado_en"]
    assert leido is not None

    # Ida y vuelta por JSON, como lo manda el front.
    servicio.editar(c.id, entrada(numero="A 0003", actualizado_en=leido.isoformat()),
                    usuario_id=OTRO_USUARIO)

    # Otra persona que había abierto el detalle antes del último guardado.
    with pytest.raises(ComprobanteModificado):
        servicio.editar(c.id, entrada(numero="A 0004", actualizado_en=None),
                        usuario_id=USUARIO)
    db.expire_all()
    sin_tocar = db.get(Comprobante, c.id)
    assert sin_tocar.numero == "A 0003"
    assert sin_tocar.actualizado_por == OTRO_USUARIO


def test_el_put_con_un_actualizado_en_viejo_no_toca_nada(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.editar(c.id, entrada(), usuario_id=USUARIO)
    db.expire_all()
    sellado = db.get(Comprobante, c.id).actualizado_en

    with pytest.raises(ComprobanteModificado):
        servicio.editar(c.id, entrada(numero="A 0009",
                                      actualizado_en=sellado - timedelta(seconds=1)),
                        usuario_id=OTRO_USUARIO)
    db.expire_all()
    sin_tocar = db.get(Comprobante, c.id)
    assert (sin_tocar.numero, sin_tocar.actualizado_en) == ("A 0001", sellado)


def test_un_nunca_editado_con_un_actualizado_en_da_modificado(servicio, db):
    c = servicio.crear(entrada(), usuario_id=USUARIO)

    with pytest.raises(ComprobanteModificado):
        servicio.editar(c.id, entrada(actualizado_en="2026-10-12T10:00:00"),
                        usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, c.id).actualizado_en is None


def test_en_el_alta_el_actualizado_en_se_ignora(servicio, db):
    c = servicio.crear(entrada(actualizado_en="2026-10-12T10:00:00"), usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, c.id).actualizado_en is None


# ─── Tarea que pasó a baja ──────────────────────────────────────────────────

def dar_de_baja_tarea(consulta, tarea_id):
    consulta.TAREAS = [t for t in ConsultaFalsa.TAREAS if t["tarea_id"] != tarea_id]


def test_una_tarea_que_paso_a_baja_se_conserva_al_editar(servicio, db, consulta):
    c = servicio.crear(entrada(lineas=[linea(), linea(tarea_id=20, unidad="horas_peon")]),
                       usuario_id=USUARIO)
    dar_de_baja_tarea(consulta, 20)

    servicio.editar(c.id, entrada(lineas=[
        linea(tarea_id=20, unidad="horas_peon", cantidad="4", precio_unitario="1"),
    ]), usuario_id=OTRO_USUARIO)
    db.expire_all()
    (unica,) = db.get(Comprobante, c.id).lineas
    # El nombre es la copia que ya tenía el Comprobante.
    assert (unica.tarea_id, unica.tarea_nombre, unica.importe) == (
        20, "TAREA B", Decimal("4.00"))


def test_una_tarea_de_baja_nueva_en_el_comprobante_es_linea_invalida(
        servicio, db, consulta):
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    dar_de_baja_tarea(consulta, 20)

    with pytest.raises(LineaInvalida) as error:
        servicio.editar(c.id, entrada(lineas=[linea(), linea(tarea_id=20,
                                                             unidad="horas_peon")]),
                        usuario_id=OTRO_USUARIO)
    assert (error.value.fila, error.value.campo) == (2, "tarea_id")


def test_una_tarea_de_baja_de_otro_comprobante_no_sirve(servicio, db, consulta):
    servicio.crear(entrada(numero="A 0002",
                           lineas=[linea(tarea_id=20, unidad="horas_peon")]),
                   usuario_id=USUARIO)
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    dar_de_baja_tarea(consulta, 20)

    with pytest.raises(LineaInvalida) as error:
        servicio.editar(c.id, entrada(lineas=[linea(tarea_id=20, unidad="horas_peon")]),
                        usuario_id=OTRO_USUARIO)
    assert (error.value.fila, error.value.campo) == (1, "tarea_id")


# ─── Borrado frenado por la base ────────────────────────────────────────────

def _commit_que_choca(db, monkeypatch):
    """Un commit que la base frena con un IntegrityError, como el de la FK de
    una Nota de crédito cargada entre el control y el DELETE (SQLite no
    controla las FK, así que se simula)."""
    def commit():
        raise IntegrityError("DELETE FROM facturacion_comprobante", {},
                             Exception("foreign key"))
    monkeypatch.setattr(db, "commit", commit)


def test_si_la_base_frena_el_borrado_por_una_nota_nueva_es_factura_con_notas(
        servicio, db, monkeypatch):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    servicio.crear(nota(factura.id), usuario_id=OTRO_USUARIO)
    real = servicio._tiene_notas
    llamadas = []

    def control_previo_ciego(comprobante_id):
        # El control previo no ve la Nota (otra persona la cargó en ese
        # momento); la búsqueda después del choque con la base sí.
        llamadas.append(comprobante_id)
        return False if len(llamadas) == 1 else real(comprobante_id)

    monkeypatch.setattr(servicio, "_tiene_notas", control_previo_ciego)
    _commit_que_choca(db, monkeypatch)

    with pytest.raises(FacturaConNotas):
        servicio.borrar(factura.id)
    assert len(llamadas) == 2
    monkeypatch.undo()
    db.expire_all()
    assert db.get(Comprobante, factura.id) is not None


def test_si_la_base_frena_el_borrado_por_otra_cosa_el_error_sigue(
        servicio, db, monkeypatch):
    c = servicio.crear(entrada(), usuario_id=USUARIO)
    _commit_que_choca(db, monkeypatch)

    with pytest.raises(IntegrityError):
        servicio.borrar(c.id)
    monkeypatch.undo()
    db.expire_all()
    assert db.get(Comprobante, c.id) is not None


# ═══ R1: dos guardados a la vez (revisión de BK-A) ══════════════════════════

@pytest.fixture()
def dos_sesiones(tmp_path):
    """Dos personas, cada una con su sesión sobre la misma base. En un archivo
    y no en memoria: SQLite en memoria comparte una sola conexión entre las
    sesiones, y acá cada una tiene que ver sólo lo que la otra confirmó."""
    engine = create_engine(f"sqlite:///{tmp_path / 'comprobantes.db'}")
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine)
    sesion_a, sesion_b = Sesion(), Sesion()
    yield sesion_a, sesion_b
    sesion_a.close()
    sesion_b.close()
    engine.dispose()


def test_dos_guardados_a_la_vez_no_mezclan_las_lineas(dos_sesiones, monkeypatch):
    # A y B abren el mismo Comprobante (nunca editado) y guardan casi a la
    # vez. Las dos pasan la comparación del principio; el guardado de A se
    # confirma mientras B consulta las tareas del campo. Si B siguiera, borraría
    # por id las Líneas que leyó (que A ya reemplazó) y sumaría las suyas: el
    # Comprobante quedaría con las de A y las de B, con el total inflado.
    sesion_a, sesion_b = dos_sesiones
    servicio_a = ComprobantesService(sesion_a, ConsultaFalsa())
    consulta_b = ConsultaFalsa()
    servicio_b = ComprobantesService(sesion_b, consulta_b)
    c = servicio_a.crear(entrada(), usuario_id=USUARIO)

    tareas_reales = consulta_b.obtener_tareas
    guardados_de_a = []

    def tareas_mientras_a_guarda(incluir_baja=False):
        if not guardados_de_a:
            guardados_de_a.append(servicio_a.editar(c.id, entrada(lineas=[
                linea(tarea_id=20, unidad="horas_peon", cantidad="2", precio_unitario="3"),
            ]), usuario_id=USUARIO))
        return tareas_reales(incluir_baja)

    monkeypatch.setattr(consulta_b, "obtener_tareas", tareas_mientras_a_guarda)

    with pytest.raises(ComprobanteModificado):
        servicio_b.editar(c.id, entrada(numero="A 0002", lineas=[
            linea(cantidad="5", precio_unitario="1"),
        ]), usuario_id=OTRO_USUARIO)
    assert len(guardados_de_a) == 1

    # Queda exactamente lo que guardó A.
    sesion_a.expire_all()
    guardado = sesion_a.get(Comprobante, c.id)
    assert (guardado.numero, guardado.actualizado_por) == ("A 0001", USUARIO)
    assert [(l.tarea_id, l.importe) for l in guardado.lineas] == [(20, Decimal("6.00"))]
    assert sesion_a.query(LineaComprobante).count() == 1


# ═══ R2: una finca que pasó a baja (revisión de BK-A) ═══════════════════════

def dar_de_baja_fincas(consulta, cliente_id):
    """Las fincas del Cliente pasan a baja en el campo después de cargar el
    Comprobante: la lectura de fincas ya no las trae."""
    consulta.FINCAS = {**consulta.FINCAS, cliente_id: []}


@pytest.fixture()
def cliente_con_dos_fincas(consulta):
    """El Cliente 1 con una segunda finca, que el Comprobante no usa."""
    consulta.FINCAS = {**ConsultaFalsa.FINCAS,
                       1: [{"id": 100, "nombre": "FINCA UNO"},
                           {"id": 101, "nombre": "FINCA UNO BIS"}]}
    return consulta


def test_una_finca_que_paso_a_baja_se_conserva_al_editar(servicio, db, consulta):
    # Corregir sólo el número no obliga a quitarle la finca a la Línea.
    c = servicio.crear(entrada(lineas=[linea(finca_id=100)]), usuario_id=USUARIO)
    dar_de_baja_fincas(consulta, 1)

    servicio.editar(c.id, entrada(numero="A 0002", lineas=[linea(finca_id=100)]),
                    usuario_id=OTRO_USUARIO)
    db.expire_all()
    guardado = db.get(Comprobante, c.id)
    (unica,) = guardado.lineas
    # El nombre es la copia que ya tenía el Comprobante.
    assert guardado.numero == "A 0002"
    assert (unica.finca_id, unica.finca_nombre) == (100, "FINCA UNO")


def test_una_finca_de_baja_nueva_en_el_comprobante_es_linea_invalida(
        servicio, db, cliente_con_dos_fincas):
    c = servicio.crear(entrada(lineas=[linea(finca_id=100)]), usuario_id=USUARIO)
    dar_de_baja_fincas(cliente_con_dos_fincas, 1)

    with pytest.raises(LineaInvalida) as error:
        servicio.editar(c.id, entrada(lineas=[linea(finca_id=100), linea(finca_id=101)]),
                        usuario_id=OTRO_USUARIO)
    assert (error.value.fila, error.value.campo) == (2, "finca_id")


def test_cambiar_de_cliente_con_una_finca_de_baja_es_linea_invalida(
        servicio, db, con_tercer_cliente):
    c = servicio.crear(entrada(lineas=[linea(finca_id=100)]), usuario_id=USUARIO)
    dar_de_baja_fincas(con_tercer_cliente, 1)

    with pytest.raises(LineaInvalida) as error:
        servicio.editar(c.id, entrada(cliente_id=3, lineas=[linea(finca_id=100)]),
                        usuario_id=OTRO_USUARIO)
    assert (error.value.fila, error.value.campo) == (1, "finca_id")
    db.expire_all()
    assert db.get(Comprobante, c.id).cliente_id == 1


# ═══ R3: Facturas y Notas de crédito numeran aparte (revisión de BK-A) ══════

def test_una_nota_con_el_numero_de_una_factura_de_la_misma_empresa_se_da_de_alta(
        servicio, db):
    factura = servicio.crear(entrada(numero="A 0001"), usuario_id=USUARIO)

    nc = servicio.crear(nota(factura.id, numero=" a 0001 "), usuario_id=USUARIO)
    db.expire_all()
    guardada = db.get(Comprobante, nc.id)
    assert (guardada.tipo, guardada.numero) == ("nota_credito", "A 0001")
    assert db.query(Comprobante).count() == 2


def test_dos_notas_con_el_mismo_numero_y_empresa_son_repetidas(servicio, db):
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    primera = servicio.crear(nota(factura.id), usuario_id=USUARIO)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.crear(nota(factura.id, numero=" nc  0001"), usuario_id=USUARIO)
    assert error.value.comprobante_id == primera.id
    assert db.query(Comprobante).count() == 2


def test_una_nota_con_el_numero_de_un_historico_del_cliente_se_da_de_alta(
        servicio, db):
    # Los históricos son siempre Facturas: la Nota numera aparte.
    viejo = historico(db)

    nc = servicio.crear(nota(viejo.id, numero="b 0007"), usuario_id=USUARIO)
    db.expire_all()
    assert db.get(Comprobante, nc.id).numero == "B 0007"
    # Una Factura con ese número sigue frenada.
    with pytest.raises(HistoricoMismoNumero) as error:
        servicio.crear(entrada(numero="B 0007"), usuario_id=USUARIO)
    assert error.value.comprobante_id == viejo.id


def test_pasar_una_factura_a_nota_con_el_numero_de_otra_nota_es_repetido(
        servicio, db):
    corregida = servicio.crear(entrada(numero="A 0001"), usuario_id=USUARIO)
    otra_nota = servicio.crear(nota(corregida.id, numero="NC 0001"), usuario_id=USUARIO)
    c = servicio.crear(entrada(numero="NC 0001"), usuario_id=USUARIO)

    with pytest.raises(ComprobanteRepetido) as error:
        servicio.editar(c.id, nota(corregida.id, numero="NC 0001"),
                        usuario_id=OTRO_USUARIO)
    assert error.value.comprobante_id == otra_nota.id
    db.expire_all()
    assert db.get(Comprobante, c.id).tipo == "factura"


# ═══ R4: una Nota cargada mientras su Factura cambia (revisión de BK-A) ═════
# Crear una Nota no toca el `actualizado_en` de la Factura, así que el UPDATE
# condicionado de R1 no la ve. SQLite no bloquea: estos tests prueban el
# orden (el control se repite después del UPDATE), no la espera de MySQL.

def _nota_de_b_mientras_a_valida(consulta_a, servicio_b, factura_id, monkeypatch):
    """La Nota de B se confirma después del primer control de Notas de A y
    antes de su UPDATE: dentro de la consulta de tareas de A."""
    tareas_reales = consulta_a.obtener_tareas
    notas_de_b = []

    def tareas_mientras_b_carga(incluir_baja=False):
        if not notas_de_b:
            notas_de_b.append(servicio_b.crear(nota(factura_id), usuario_id=OTRO_USUARIO))
        return tareas_reales(incluir_baja)

    monkeypatch.setattr(consulta_a, "obtener_tareas", tareas_mientras_b_carga)
    return notas_de_b


def _sigue_siendo_factura_del_cliente_1(sesion, factura_id, notas_de_b):
    assert len(notas_de_b) == 1
    sesion.expire_all()
    factura = sesion.get(Comprobante, factura_id)
    assert (factura.tipo, factura.cliente_id, factura.numero) == ("factura", 1, "A 0001")
    assert factura.actualizado_en is None
    assert sesion.get(Comprobante, notas_de_b[0].id).factura_corregida_id == factura_id


def test_una_nota_cargada_mientras_la_factura_pasa_a_nota_frena_el_cambio(
        dos_sesiones, monkeypatch):
    sesion_a, sesion_b = dos_sesiones
    consulta_a = ConsultaFalsa()
    servicio_a = ComprobantesService(sesion_a, consulta_a)
    servicio_b = ComprobantesService(sesion_b, ConsultaFalsa())
    factura = servicio_a.crear(entrada(numero="A 0001"), usuario_id=USUARIO)
    otra = servicio_a.crear(entrada(numero="A 0002"), usuario_id=USUARIO)
    notas_de_b = _nota_de_b_mientras_a_valida(consulta_a, servicio_b, factura.id,
                                              monkeypatch)

    with pytest.raises(FacturaConNotas):
        servicio_a.editar(factura.id, nota(otra.id, numero="A 0001"),
                          usuario_id=USUARIO)
    _sigue_siendo_factura_del_cliente_1(sesion_a, factura.id, notas_de_b)


def test_una_nota_cargada_mientras_la_factura_cambia_de_cliente_frena_el_cambio(
        dos_sesiones, monkeypatch):
    sesion_a, sesion_b = dos_sesiones
    consulta_a = ConsultaFalsa()
    consulta_a.CLIENTES = ConsultaFalsa.CLIENTES + [TERCERO]
    servicio_a = ComprobantesService(sesion_a, consulta_a)
    servicio_b = ComprobantesService(sesion_b, ConsultaFalsa())
    factura = servicio_a.crear(entrada(numero="A 0001"), usuario_id=USUARIO)
    notas_de_b = _nota_de_b_mientras_a_valida(consulta_a, servicio_b, factura.id,
                                              monkeypatch)

    with pytest.raises(FacturaConNotas):
        servicio_a.editar(factura.id, entrada(cliente_id=3, numero="A 0001"),
                          usuario_id=USUARIO)
    _sigue_siendo_factura_del_cliente_1(sesion_a, factura.id, notas_de_b)


def test_la_factura_que_corrige_una_nota_se_lee_con_bloqueo_compartido(servicio, db):
    # El otro lado de la carrera: en MySQL, la Nota espera a que la edición
    # de su Factura se confirme y valida contra lo confirmado. SQLite no
    # bloquea, así que se mira la lectura compilada para MySQL.
    factura = servicio.crear(entrada(), usuario_id=USUARIO)
    lecturas = []

    @event.listens_for(db, "do_orm_execute")
    def anotar(estado):
        if estado.is_select:
            lecturas.append(str(estado.statement.compile(dialect=mysql.dialect())))

    servicio.crear(nota(factura.id), usuario_id=USUARIO)
    bloqueantes = [l for l in lecturas if "LOCK IN SHARE MODE" in l or "FOR SHARE" in l]
    assert len(bloqueantes) == 1
    assert "facturacion_comprobante.id = " in bloqueantes[0]
