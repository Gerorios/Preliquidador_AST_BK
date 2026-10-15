"""Las tarifas y los seguros atados al id de la máquina, no a su nombre.

Al reorganizar el maestro de maquinaria del sistema de campo cambiaron los
nombres de las máquinas, y cientos de tarifas dejaron de encontrar la suya
(2026-10-07). Lo que cuidan estos tests es que **un renombre no rompa nada**:
la fila del hecho no se rehace, la tarifa sigue cobrando y el seguro sigue a su
bien, con el nombre y el dueño nuevos.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import (
    CALCULADO, HoraServicio, PrecioSeguro, TarifaServicio,
)
from app.modulos.terceros.services.calculo_service import CalculoService
from app.modulos.terceros.services.liquidacion_service import LiquidacionService
from app.modulos.terceros.services.tarifario_service import TarifarioService
from tests.terceros.test_liquidacion_service import (
    ExternaFalsa, TallerFalso, servicio_fila,
)

Q = date(2026, 8, 1)
S = date(2026, 8, 16)
VIEJO = "MANITOU MANITOU N°0060 ROLDAN"
NUEVO = "CARGADORA MANITOU N°0060 ROLDAN"


class Externa(ExternaFalsa):
    """El sistema de campo, con un padrón de bienes que se puede cambiar."""

    def __init__(self, bienes=(), **kw):
        super().__init__(**kw)
        self.bienes = list(bienes)

    def bienes_terceros(self):
        return self.bienes


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # Sin vaciado automático, como la sesión de la app (SessionPropia): con él,
    # estos tests pasaban aunque el renombre llegara una actualización tarde.
    sesion = sessionmaker(bind=engine, autoflush=False)()
    yield sesion
    sesion.close()


def hora(nombre):
    return {**servicio_fila(maquinaria=nombre), "id_maquinaria": 615, "tercero": "ROLDAN"}


def generar(db, externa, quincena=Q):
    LiquidacionService(db, externa, TallerFalso()).generar(quincena)


# ─── El hecho ───────────────────────────────────────────────────────────────

def test_la_hora_de_servicio_guarda_el_id_de_su_maquina(db):
    generar(db, Externa(servicios=[hora(VIEJO)]))
    assert db.query(HoraServicio).one().id_maquinaria == 615


def test_renombrar_la_maquina_no_rehace_la_hora_ni_pierde_lo_movido(db):
    externa = Externa(servicios=[hora(VIEJO)])
    generar(db, externa)
    h = db.query(HoraServicio).one()
    h.quincena_efectiva, h.motivo_efectiva = S, "se cobra en la otra"
    db.commit()
    id_antes = h.id

    externa._servicios = [hora(NUEVO)]
    generar(db, externa)
    h = db.query(HoraServicio).one()
    assert (h.id, h.maquinaria, h.quincena_efectiva) == (id_antes, NUEVO, S)


# ─── La tarifa ──────────────────────────────────────────────────────────────

def test_la_tarifa_toma_el_id_de_la_maquina_que_trabajo(db):
    generar(db, Externa(servicios=[hora(VIEJO)]))
    t = TarifarioService(db).crear("servicio", Q, {
        "maquinaria": VIEJO, "precio": "10000", "unidad_base": "hsmaquina"})
    assert t.id_maquinaria == 615


def test_la_tarifa_sigue_a_su_maquina_cuando_le_cambian_el_nombre(db):
    externa = Externa(servicios=[hora(VIEJO)])
    generar(db, externa)
    TarifarioService(db).crear("servicio", Q, {
        "maquinaria": VIEJO, "precio": "10000", "unidad_base": "hsmaquina"})

    externa._servicios = [hora(NUEVO)]
    generar(db, externa)
    CalculoService(db).calcular(Q)
    assert db.query(TarifaServicio).one().maquinaria == NUEVO
    h = db.query(HoraServicio).one()
    assert (h.estado_calculo, h.importe) == (CALCULADO, Decimal("60000.00"))


def test_la_tarifa_toma_el_dueno_nuevo_cuando_lo_corrigen_en_el_campo(db):
    """Corregir cómo está escrito el dueño ("ANA FERREYRA" a "FERREYRA, ANA") no
    puede dejar sin precio las horas de su máquina (2026-10-14)."""
    externa = Externa(servicios=[{**hora(VIEJO), "tercero": "ANA FERREYRA"}])
    generar(db, externa)
    TarifarioService(db).crear("servicio", Q, {
        "tercero": "ANA FERREYRA", "maquinaria": VIEJO, "precio": "10000",
        "unidad_base": "hsmaquina"})

    externa._servicios = [{**hora(VIEJO), "tercero": "FERREYRA, ANA"}]
    generar(db, externa)
    CalculoService(db).calcular(Q)
    assert db.query(TarifaServicio).one().tercero == "FERREYRA, ANA"
    assert db.query(HoraServicio).one().estado_calculo == CALCULADO


def test_una_tarifa_sin_tercero_sigue_valiendo_para_cualquiera(db):
    externa = Externa(servicios=[hora(VIEJO)])
    generar(db, externa)
    TarifarioService(db).crear("servicio", Q, {
        "maquinaria": VIEJO, "precio": "10000", "unidad_base": "hsmaquina"})

    externa._servicios = [{**hora(VIEJO), "tercero": "OTRO SRL"}]
    generar(db, externa)
    assert not db.query(TarifaServicio).one().tercero


def test_una_tarifa_a_nombre_de_otro_tercero_no_pasa_al_dueno(db):
    """Hay reglas de una máquina a nombre de otros terceros (cargadas en lote):
    no son del dueño, y pasarlas a él las haría chocar entre sí."""
    externa = Externa(servicios=[{**hora(VIEJO), "tercero": "ANA FERREYRA"}])
    generar(db, externa)
    tarifario = TarifarioService(db)
    for tercero in ("ANA FERREYRA", "SOSA, MARTA", "VEGA, RAUL"):
        tarifario.crear("servicio", Q, {"tercero": tercero, "maquinaria": VIEJO,
                                        "precio": "10000", "unidad_base": "hsmaquina"})

    externa._servicios = [{**hora(NUEVO), "tercero": "FERREYRA, ANA"}]
    generar(db, externa)
    assert sorted((t.tercero, t.maquinaria) for t in db.query(TarifaServicio)) == [
        ("FERREYRA, ANA", NUEVO), ("SOSA, MARTA", NUEVO), ("VEGA, RAUL", NUEVO)]


def test_dos_reglas_que_pasan_al_mismo_nombre_no_rompen_la_actualizacion(db):
    """La misma máquina con dos reglas, una con el dueño escrito de cada forma:
    pasa una sola y la otra queda como está, a la vista."""
    externa = Externa(servicios=[{**hora(VIEJO), "tercero": "ANA FERREYRA"}])
    generar(db, externa)
    tarifario = TarifarioService(db)
    for tercero in ("ANA FERREYRA", "FERREYRA ANA"):
        tarifario.crear("servicio", Q, {"tercero": tercero, "maquinaria": VIEJO,
                                        "precio": "10000", "unidad_base": "hsmaquina"})

    externa._servicios = [{**hora(VIEJO), "tercero": "FERREYRA, ANA"}]
    generar(db, externa)
    terceros = [t.tercero for t in db.query(TarifaServicio)]
    assert len(terceros) == 2 and terceros.count("FERREYRA, ANA") == 1


def test_una_maquina_sin_dueno_no_le_borra_el_tercero_a_la_tarifa(db):
    externa = Externa(servicios=[hora(VIEJO)])
    generar(db, externa)
    TarifarioService(db).crear("servicio", Q, {
        "tercero": "ROLDAN", "maquinaria": VIEJO, "precio": "10000",
        "unidad_base": "hsmaquina"})

    externa._servicios = [{**hora(VIEJO), "tercero": None}]
    generar(db, externa)
    assert db.query(TarifaServicio).one().tercero == "ROLDAN"


def test_no_pisa_una_regla_que_ya_tiene_el_nombre_nuevo(db):
    """Dos reglas iguales dejarían el precio ambiguo: la vieja queda como está,
    a la vista, y gana la que alguien cargó con el nombre nuevo."""
    externa = Externa(servicios=[hora(VIEJO)])
    generar(db, externa)
    tarifario = TarifarioService(db)
    tarifario.crear("servicio", Q, {"maquinaria": VIEJO, "precio": "10000",
                                    "unidad_base": "hsmaquina"})
    tarifario.crear("servicio", Q, {"maquinaria": NUEVO, "precio": "12000",
                                    "unidad_base": "hsmaquina"})

    externa._servicios = [hora(NUEVO)]
    generar(db, externa)
    assert sorted(t.maquinaria for t in db.query(TarifaServicio)) == sorted([VIEJO, NUEVO])


def test_copiar_la_tarifa_copia_su_id(db):
    generar(db, Externa(servicios=[hora(VIEJO)]))
    tarifario = TarifarioService(db)
    tarifario.crear("servicio", Q, {"maquinaria": VIEJO, "precio": "10000",
                                    "unidad_base": "hsmaquina"})
    tarifario.copiar(Q, S)
    copia = db.query(TarifaServicio).filter(TarifaServicio.quincena == S).one()
    assert copia.id_maquinaria == 615


# ─── El seguro ──────────────────────────────────────────────────────────────

def bien(origen, id_, tercero, nombre, patente=None):
    return {"origen": origen, "id_origen": id_, "tercero": tercero,
            "nombre": nombre, "patente": patente, "detalle": None}


def seguro(db, tercero, sujeto, origen, id_):
    return TarifarioService(db).crear("seguros", S, {
        "tercero": tercero, "tipo_seguro": "AUTOMOTOR", "sujeto": sujeto,
        "origen": origen, "id_origen": id_, "importe": "10375.51"})


def test_el_seguro_sigue_a_su_maquina_con_el_nombre_y_el_dueno_nuevos(db):
    s = seguro(db, "JOSE PENA", "TRACTOR DEUTZ N°0001 JOSE PEÑA", "maquinaria", 515)
    assert (s.origen, s.id_origen) == ("maquinaria", 515)

    generar(db, Externa(bienes=[bien("maquinaria", 515, "JOSE PEÑA",
                                     "TRACTOR DEUTZ 460 N°0001 JOSE PEÑA")]))
    s = db.query(PrecioSeguro).one()
    assert (s.tercero, s.sujeto) == ("JOSE PEÑA", "TRACTOR DEUTZ 460 N°0001 JOSE PEÑA")


def test_el_seguro_de_un_colectivo_toma_el_dueno_y_la_patente_del_padron(db):
    seguro(db, "QUIROGA LUIS", "COLECTIVO ZZZ999", "colectivo", 45)
    generar(db, Externa(bienes=[bien("colectivo", 45, "QUIROGA, LUIS",
                                     "COLECTIVO ZZZ999", "ZZZ999")]))
    s = db.query(PrecioSeguro).one()
    assert (s.tercero, s.referencia) == ("QUIROGA, LUIS", "ZZZ999")


def test_el_seguro_de_un_chofer_no_se_toca(db):
    """El mismo chofer aparece con cada dueño para el que manejó: su id no dice
    de quién es la póliza."""
    seguro(db, "QUIROGA, LUIS", "PEREZ, JUAN", "chofer", 900)
    generar(db, Externa(bienes=[bien("chofer", 900, "VEGA, RAUL", "PEREZ, JUAN")]))
    assert db.query(PrecioSeguro).one().tercero == "QUIROGA, LUIS"


def test_un_seguro_cargado_a_mano_sin_bien_no_se_toca(db):
    TarifarioService(db).crear("seguros", S, {
        "tercero": "EMPRESA 0001", "tipo_seguro": "AUTOMOTOR", "sujeto": "ACOPLADO",
        "importe": "5000"})
    generar(db, Externa(bienes=[bien("maquinaria", 1, "OTRO", "ACOPLADO")]))
    assert db.query(PrecioSeguro).one().tercero == "EMPRESA 0001"
