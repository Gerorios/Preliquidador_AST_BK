"""Generar y actualizar una quincena (etapa 5).

Lo que importa acá es la reconciliación: que actualizar no borre y vuelva a
cargar, que sea idempotente, y que respete lo que el liquidador cargó a mano.
Base SQLite en memoria y orígenes falsos — no hay base real ni red.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CargaCombustible, HoraReparacion, HoraServicio, Liquidacion, Repuesto, Viaje,
)
from app.modulos.terceros.services.liquidacion_service import LiquidacionService

Q = date(2026, 8, 1)


def viaje(patente="FAP480", cliente="SAN MIGUEL", finca="CASPINCHANGO", viajes="1.00",
          fecha="2026-08-01", capataz="SOSA", personas=32):
    return {
        "fecha_uso": fecha, "fecha_carga": fecha, "quincena_mes": "08-1Q",
        "colectivo_nombre": "ARANDA, HUGO", "colectivo_patente": patente,
        "colectivo_propiedad": "TERCEROS", "cliente": cliente, "finca": finca,
        "nombre_tarea": "COSECHA LIMON HORAS", "nombre_supervisor": "SORIA",
        "nombre_capataz": capataz, "nombre_chofer": "ACOSTA",
        "cantidadviajes": Decimal(viajes), "cantpersonas": personas,
    }


def carga(vale="60023", litros="150"):
    return {
        "fecha_uso": "2026-08-03", "fecha_carga": "2026-08-04", "quincena_mes": "08-1Q",
        "colectivo_nombre": "ARANDA, HUGO", "colectivo_patente": " FAP480",
        "colectivo_propiedad": "TERCEROS", "litros_cargados": litros, "vale": vale,
        "origen_combustible": "SHELL", "usuario_carga": "SORIA",
    }


def servicio_fila(maquinaria="MANITOU N°0060 BARRIOS", horas="6.00", unidades="297.00"):
    return {
        "fecha": date(2026, 8, 1), "quincena_mes": "08-1Q", "planilla": "MAQUINARIA",
        "cliente": "CITRUSVIL", "finca": "CASPINCHANGO", "tarea": "CARGA FRUTA POR BINS",
        "maquinaria": maquinaria, "tercero": "BARRIOS", "supervisor": "RIVAS",
        "horas_maquina": Decimal(horas), "unidades": Decimal(unidades), "unidad": "BINS",
    }


def repuesto(nombre="TORNILLO", monto="789.81"):
    return {
        "id_maquina": 721, "maquina": "MAQUINARIA RUBEN MUÑOZ", "fecha": date(2026, 8, 5),
        "fecha_descarga": date(2026, 8, 14), "quincena_mes": "08-1Q",
        "tipo_insumo": "REPUESTOS", "rubro": "BULONERIA", "repuesto": nombre,
        "cantidad": Decimal("3.00"), "precargas": Decimal("263.27"),
        "monto_total": Decimal(monto), "reparacion": "", "nombreprove": "BULONERIA SRL",
        "propiedad_maquina": "TERCEROS",
    }


def reparacion(sub="475. TORRE", total="5.0"):
    return {
        "fecha": date(2026, 8, 3), "quincena_mes": "08-1Q", "anio": 2026,
        "tercero": "PABLO ROJAS", "maquina": "CARGADORA MANITOU N°9872 PABLO ROJAS",
        "tipo_maquina": "CARGADORAS", "rubro": "HIDRAULICA", "sub_rubro": sub,
        "finca": "EL CORTE", "lugar": "CAMPO", "estado": "Pendiente",
        "horas": 2.0, "horas_preparacion": 1.0, "horas_traslado": 2.0,
        "horas_total": float(total), "id_maquina": 735,
    }


class ExternaFalsa:
    def __init__(self, viajes=(), cargas=(), servicios=(), repuestos=()):
        self._viajes, self._cargas = list(viajes), list(cargas)
        self._servicios, self._repuestos = list(servicios), list(repuestos)

    def viajes(self, q):
        return self._viajes

    def cargas_combustible(self, q):
        return self._cargas

    def horas_servicio(self, q):
        return self._servicios

    def repuestos(self, q):
        return self._repuestos


class TallerFalso:
    def __init__(self, filas=()):
        self._filas = list(filas)

    def horas_quincena(self, q):
        return self._filas


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def armar(db, **kwargs):
    externa = ExternaFalsa(
        viajes=kwargs.get("viajes", ()), cargas=kwargs.get("cargas", ()),
        servicios=kwargs.get("servicios", ()), repuestos=kwargs.get("repuestos", ()),
    )
    return LiquidacionService(db, externa, TallerFalso(kwargs.get("reparaciones", ())))


# ─── Generar ────────────────────────────────────────────────────────────────

def test_generar_crea_la_quincena_y_guarda_los_cinco_conjuntos(db):
    s = armar(db, viajes=[viaje()], cargas=[carga()], servicios=[servicio_fila()],
              repuestos=[repuesto()], reparaciones=[reparacion()])
    r = s.generar(Q, usuario_id=None)

    assert r["nueva"] is True
    assert r["filas"] == {"viajes": 1, "horas_servicio": 1, "combustible": 1,
                          "repuestos": 1, "horas_reparacion": 1}
    assert db.query(Liquidacion).count() == 1


def test_el_tercero_de_un_viaje_sale_del_nombre_del_colectivo(db):
    """En el sistema de campo el nombre del colectivo ES el de su dueño."""
    armar(db, viajes=[viaje()]).generar(Q)
    assert db.query(Viaje).one().tercero == "ARANDA, HUGO"


def test_la_patente_se_guarda_sin_los_espacios_del_origen(db):
    armar(db, cargas=[carga()]).generar(Q)
    assert db.query(CargaCombustible).one().colectivo_patente == "FAP480"


def test_el_tercero_de_un_repuesto_se_deduce_del_nombre_de_la_maquina(db):
    """El sistema de compras no guarda el dueño. Se usa la misma heurística que
    la app del taller, con lo frágil que es: por eso el plan pide un campo."""
    armar(db, repuestos=[repuesto()]).generar(Q)
    assert db.query(Repuesto).one().tercero == "RUBEN MUÑOZ"


def test_las_dos_fechas_del_repuesto_se_guardan(db):
    armar(db, repuestos=[repuesto()]).generar(Q)
    r = db.query(Repuesto).one()
    assert r.fecha == date(2026, 8, 5) and r.fecha_descarga == date(2026, 8, 14)


def test_la_hora_de_servicio_guarda_las_dos_medidas_y_la_unidad(db):
    armar(db, servicios=[servicio_fila()]).generar(Q)
    h = db.query(HoraServicio).one()
    assert h.horas_maquina == Decimal("6.00")
    assert h.unidades == Decimal("297.00")
    assert h.unidad == "BINS"


# ─── Actualizar: reconciliación ─────────────────────────────────────────────

def test_actualizar_sin_cambios_no_toca_una_sola_fila(db):
    """Es la propiedad que hace que se pueda apretar Actualizar sin miedo."""
    s = armar(db, viajes=[viaje(), viaje(cliente="CITROMAX")], cargas=[carga()],
              servicios=[servicio_fila()], repuestos=[repuesto()],
              reparaciones=[reparacion()])
    s.generar(Q)
    ids = sorted(v.id for v in db.query(Viaje).all())

    r = s.generar(Q)

    assert r["nueva"] is False
    assert all(d["insertadas"] == 0 and d["borradas"] == 0 for d in r["detalle"].values())
    assert sorted(v.id for v in db.query(Viaje).all()) == ids


def test_un_hecho_nuevo_en_el_origen_se_suma(db):
    """El caso de todos los días: alguien carga un viaje después de generar."""
    externa = ExternaFalsa(viajes=[viaje()])
    s = LiquidacionService(db, externa, TallerFalso())
    s.generar(Q)

    externa._viajes.append(viaje(cliente="CITROMAX"))
    r = s.generar(Q)

    assert r["detalle"]["viajes"]["insertadas"] == 1
    assert db.query(Viaje).count() == 2


def test_un_hecho_que_desaparecio_del_origen_se_borra(db):
    externa = ExternaFalsa(viajes=[viaje(), viaje(cliente="CITROMAX")])
    s = LiquidacionService(db, externa, TallerFalso())
    s.generar(Q)

    externa._viajes.pop()
    r = s.generar(Q)

    assert r["detalle"]["viajes"]["borradas"] == 1
    assert db.query(Viaje).count() == 1


def test_dos_hechos_iguales_no_se_pisan(db):
    """Un colectivo puede hacer dos viajes idénticos el mismo día. Si la clave
    los tratara como uno, se perdería plata."""
    armar(db, viajes=[viaje(), viaje()]).generar(Q)
    assert db.query(Viaje).count() == 2


# ─── El trabajo manual ──────────────────────────────────────────────────────

def test_actualizar_no_pisa_la_quincena_efectiva(db):
    s = armar(db, viajes=[viaje()])
    s.generar(Q)
    v = db.query(Viaje).one()
    v.quincena_efectiva = date(2026, 8, 16)
    v.motivo_efectiva = "llegó tarde"
    db.commit()

    s.generar(Q)

    v = db.query(Viaje).one()
    assert v.quincena_efectiva == date(2026, 8, 16)
    assert v.motivo_efectiva == "llegó tarde"


def test_si_hay_que_borrar_se_sacrifica_primero_la_que_no_tiene_nada_a_mano(db):
    """Dos hechos idénticos, uno con trabajo manual. Si el origen pasa a tener
    uno solo, tiene que sobrevivir el que alguien tocó."""
    externa = ExternaFalsa(viajes=[viaje(), viaje()])
    s = LiquidacionService(db, externa, TallerFalso())
    s.generar(Q)

    con_manual = db.query(Viaje).order_by(Viaje.id).first()
    con_manual.motivo_efectiva = "acordado con el dueño"
    db.commit()
    id_protegido = con_manual.id

    externa._viajes.pop()
    s.generar(Q)

    quedan = db.query(Viaje).all()
    assert len(quedan) == 1
    assert quedan[0].id == id_protegido


def test_la_marca_de_no_cobrar_tambien_protege(db):
    externa = ExternaFalsa(repuestos=[repuesto(), repuesto()])
    s = LiquidacionService(db, externa, TallerFalso())
    s.generar(Q)

    protegido = db.query(Repuesto).order_by(Repuesto.id).first()
    protegido.no_cobrar = True
    protegido.motivo_no_cobrar = "es de Citrusvil, no se le cobra"
    db.commit()
    id_protegido = protegido.id

    externa._repuestos.pop()
    s.generar(Q)

    assert [r.id for r in db.query(Repuesto).all()] == [id_protegido]


def test_si_no_alcanza_con_las_libres_se_borra_una_protegida(db):
    """El origen manda: si ya no está, no se liquida, aunque tuviera un motivo
    cargado. Lo contrario dejaría filas fantasma que nadie puede sacar."""
    externa = ExternaFalsa(viajes=[viaje()])
    s = LiquidacionService(db, externa, TallerFalso())
    s.generar(Q)
    v = db.query(Viaje).one()
    v.motivo_efectiva = "algo"
    db.commit()

    externa._viajes.clear()
    s.generar(Q)

    assert db.query(Viaje).count() == 0


# ─── El listado del dashboard ───────────────────────────────────────────────

def test_listar_devuelve_las_quincenas_de_la_mas_nueva_a_la_mas_vieja(db):
    s = armar(db, viajes=[viaje()])
    s.generar(date(2026, 7, 16))
    s.generar(date(2026, 8, 1))
    s.generar(date(2026, 7, 1))

    assert [q["quincena"] for q in s.listar()] == [
        date(2026, 8, 1), date(2026, 7, 16), date(2026, 7, 1)]


def test_el_listado_cuenta_las_filas_de_cada_conjunto(db):
    s = armar(db, viajes=[viaje(), viaje(cliente="X")], repuestos=[repuesto()])
    s.generar(Q)
    q = s.listar()[0]
    assert q["filas"]["viajes"] == 2
    assert q["filas"]["repuestos"] == 1
    assert q["total_filas"] == 3


def test_generar_de_nuevo_marca_cuando_se_actualizo(db):
    s = armar(db, viajes=[viaje()])
    s.generar(Q)
    assert s.listar()[0]["actualizada_en"] is None
    s.generar(Q)
    assert s.listar()[0]["actualizada_en"] is not None


# ─── Refrescar lo que el origen corrige ─────────────────────────────────────

def test_actualizar_trae_la_correccion_del_dueno_hecha_en_el_origen(db):
    """El dueño no está en la clave de un viaje —la clave usa la patente—, así
    que sin refrescar, corregir la ficha en el sistema de campo no llegaba
    nunca: la fila ya existía, no sobraba ni faltaba, y se quedaba vieja."""
    mal = dict(viaje(), colectivo_nombre="MARELLI, HUGO")
    armar(db, viajes=[mal]).generar(Q)
    assert db.query(Viaje).one().tercero == "MARELLI, HUGO"

    bien = dict(viaje(), colectivo_nombre="MARELI, HUGO")
    r = armar(db, viajes=[bien]).generar(Q)

    guardado = db.query(Viaje).one()
    assert guardado.tercero == "MARELI, HUGO"
    assert guardado.colectivo_nombre == "MARELI, HUGO"
    assert r["detalle"]["viajes"]["refrescadas"] == 1
    # No se rehízo: es la misma fila.
    assert r["detalle"]["viajes"]["insertadas"] == 0
    assert r["detalle"]["viajes"]["borradas"] == 0


def test_refrescar_no_pisa_lo_que_el_liquidador_cargo_a_mano(db):
    """Es lo que separa actualizar de rehacer."""
    armar(db, viajes=[dict(viaje(), colectivo_nombre="MARELLI, HUGO")]).generar(Q)
    fila = db.query(Viaje).one()
    fila.quincena_efectiva = date(2026, 8, 16)
    fila.motivo_efectiva = "llegó tarde"
    db.commit()

    armar(db, viajes=[dict(viaje(), colectivo_nombre="MARELI, HUGO")]).generar(Q)

    fila = db.query(Viaje).one()
    assert fila.tercero == "MARELI, HUGO"           # el origen manda
    assert fila.quincena_efectiva == date(2026, 8, 16)  # la persona también
    assert fila.motivo_efectiva == "llegó tarde"


def test_una_marca_de_no_cobrar_sobrevive_a_una_actualizacion(db):
    """El mapeo del origen trae `no_cobrar` en False siempre: refrescarlo sería
    pisar la decisión de no cobrarle algo a alguien."""
    armar(db, repuestos=[repuesto()]).generar(Q)
    fila = db.query(Repuesto).one()
    fila.no_cobrar = True
    fila.motivo_no_cobrar = "lo puso la empresa"
    db.commit()

    # El origen cambia algo que sí es suyo, en la misma fila.
    armar(db, repuestos=[dict(repuesto(), maquina="MAQUINARIA C. MUÑOZ")]).generar(Q)

    fila = db.query(Repuesto).one()
    assert fila.maquina == "MAQUINARIA C. MUÑOZ"
    assert fila.no_cobrar is True
    assert fila.motivo_no_cobrar == "lo puso la empresa"


def test_si_el_origen_no_cambio_nada_no_se_refresca_nada(db):
    """Actualizar dos veces seguidas no tiene que marcar cambios fantasma."""
    armar(db, viajes=[viaje()]).generar(Q)
    r = armar(db, viajes=[viaje()]).generar(Q)
    assert r["detalle"]["viajes"]["refrescadas"] == 0
    assert r["detalle"]["viajes"]["sin_cambios"] == 1


def test_los_litros_que_llegan_como_texto_no_parecen_un_cambio(db):
    """El sistema de campo manda los litros como `'150'` y se guardan como
    Decimal('150.00'). Comparándolos crudos, cada carga parecía cambiar en cada
    actualización: 130 refrescos falsos en una quincena de agosto."""
    armar(db, cargas=[carga(litros="150")]).generar(Q)
    r = armar(db, cargas=[carga(litros="150")]).generar(Q)
    assert r["detalle"]["combustible"]["refrescadas"] == 0


def test_un_cambio_de_verdad_en_un_numero_si_se_refresca(db):
    """Y el mismo campo, cuando cambia en serio, tiene que llegar."""
    armar(db, cargas=[carga(vale="60023", litros="150")]).generar(Q)
    r = armar(db, cargas=[carga(vale="60023", litros="160")]).generar(Q)
    # Los litros son parte de la clave, así que un cambio ahí es otra carga.
    assert r["detalle"]["combustible"]["insertadas"] == 1
    assert r["detalle"]["combustible"]["borradas"] == 1


# ─── Los repuestos repartidos en cuotas ────────────────────────────────────

def _repartido(db, cuotas=3):
    """Un repuesto generado, calculado y repartido en cuotas."""
    from app.modulos.terceros.services.calculo_service import CalculoService
    from app.modulos.terceros.services.destino_service import DestinoService

    CalculoService(db).calcular(Q, ("repuestos",))
    r = db.query(Repuesto).one()
    DestinoService(db).repartir_en_cuotas(r.id, Q, cuotas)
    return r


def test_actualizar_no_toca_las_cuotas_de_un_repuesto_que_sigue(db):
    from app.modulos.terceros.models import CuotaRepuesto

    s = armar(db, repuestos=[repuesto()])
    s.generar(Q)
    _repartido(db)

    r = s.generar(Q)
    assert db.query(CuotaRepuesto).count() == 3
    assert r["detalle"]["repuestos"]["planes_de_cuotas_borrados"] == 0


def test_si_el_repuesto_desaparece_de_compras_se_va_con_su_plan_y_se_avisa(db):
    """Sin repuesto no hay qué descontar. Pero es un descuento que deja de
    hacerse, y eso tiene que verse en el resultado de actualizar."""
    from app.modulos.terceros.models import CuotaRepuesto

    armar(db, repuestos=[repuesto()]).generar(Q)
    _repartido(db)

    r = armar(db, repuestos=[]).generar(Q)
    assert db.query(Repuesto).count() == 0
    assert db.query(CuotaRepuesto).count() == 0
    assert r["detalle"]["repuestos"]["planes_de_cuotas_borrados"] == 1


def test_con_dos_repuestos_iguales_se_borra_primero_el_que_no_tiene_cuotas(db):
    """Un plan de cuotas es trabajo manual aunque viva en otra tabla."""
    from app.modulos.terceros.models import CuotaRepuesto
    from app.modulos.terceros.services.calculo_service import CalculoService
    from app.modulos.terceros.services.destino_service import DestinoService

    armar(db, repuestos=[repuesto(), repuesto()]).generar(Q)
    CalculoService(db).calcular(Q, ("repuestos",))
    primero = db.query(Repuesto).order_by(Repuesto.id).first()
    DestinoService(db).repartir_en_cuotas(primero.id, Q, 2)

    armar(db, repuestos=[repuesto()]).generar(Q)
    assert [r.id for r in db.query(Repuesto).all()] == [primero.id]
    assert db.query(CuotaRepuesto).count() == 2
