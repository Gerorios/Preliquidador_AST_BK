"""La primera carga de Unidades sugeridas desde el maestro de tareas (plan de la
E1, D7): la lógica pura, sin el script.

El CSV se escribe en tmp_path con los defectos del archivo real: BOM, dobles
espacios, espacios al final y minúsculas. Los nombres de tareas son
inventados; el CSV real está fuera de git.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modulos.facturacion.models import TareaFacturacion
from app.modulos.facturacion.services.primera_carga import (
    MaestroInvalido,
    aplicar,
    definidas,
    leer_maestro,
    planificar,
)

ENCABEZADO = "nombre_tarea;grupo_tarea;grupo_factura"


def escribir_csv(tmp_path, lineas, encabezado=ENCABEZADO):
    ruta = tmp_path / "maestro.csv"
    # utf-8-sig escribe el BOM; CRLF como el archivo real.
    ruta.write_text("\r\n".join([encabezado, *lineas]) + "\r\n", encoding="utf-8-sig")
    return ruta


def tarea(tarea_id, nombre):
    return {"tarea_id": tarea_id, "nombre": nombre, "grupo_tarea": None}


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _cargadas(plan):
    return {c["tarea_id"]: (c["unidad_sugerida"], c["no_facturable"]) for c in plan.a_cargar}


# ─── Lectura ────────────────────────────────────────────────────────────────

def test_lee_el_formato_con_bom(tmp_path):
    ruta = escribir_csv(tmp_path, ["Tarea Uno;Grupo A;HORAS PEON", "Tarea Dos;;NO FACTURABLE"])
    filas = leer_maestro(ruta)
    assert filas == [
        {"nombre_tarea": "Tarea Uno", "grupo_tarea": "Grupo A", "grupo_factura": "HORAS PEON"},
        {"nombre_tarea": "Tarea Dos", "grupo_tarea": "", "grupo_factura": "NO FACTURABLE"},
    ]


def test_rechaza_otro_encabezado_con_un_error_claro(tmp_path):
    ruta = escribir_csv(tmp_path, ["Tarea Uno;HORAS PEON"], encabezado="tarea;unidad")
    with pytest.raises(MaestroInvalido) as exc:
        leer_maestro(ruta)
    assert "nombre_tarea;grupo_tarea;grupo_factura" in str(exc.value)


def test_un_archivo_vacio_tambien_es_un_error_claro(tmp_path):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text("", encoding="utf-8")
    with pytest.raises(MaestroInvalido):
        leer_maestro(ruta)


# ─── Cruce y traducción ─────────────────────────────────────────────────────

def test_cruza_por_el_nombre_normalizado_de_los_dos_lados(tmp_path):
    ruta = escribir_csv(tmp_path, ["  tarea   uno ;Grupo A;horas  peon "])
    campo = [tarea(1, "TAREA UNO "), tarea(2, "OTRA TAREA")]
    plan = planificar(leer_maestro(ruta), campo, {})
    assert _cargadas(plan) == {1: ("horas_peon", False)}


@pytest.mark.parametrize("texto, unidad", [
    ("HORAS PEON", "horas_peon"),
    ("HORAS TRACTOR", "horas_tractor"),
    ("PLANTA", "plantas"),
    ("HECTAREA", "hectareas"),
    ("TANCADA", "tancadas"),
    ("BINS", "bins"),
    ("BINS C", "bins_c"),
    ("BINS M", "bins_m"),
    ("VIAJES", "viajes"),
])
def test_traduce_los_nueve_textos_a_unidad_sugerida(texto, unidad):
    filas = [{"nombre_tarea": "TAREA UNO", "grupo_tarea": "", "grupo_factura": texto}]
    plan = planificar(filas, [tarea(1, "TAREA UNO")], {})
    assert _cargadas(plan) == {1: (unidad, False)}


def test_no_facturable_es_la_marca(tmp_path):
    ruta = escribir_csv(tmp_path, ["Tarea Uno;;no facturable"])
    plan = planificar(leer_maestro(ruta), [tarea(1, "TAREA UNO")], {})
    assert _cargadas(plan) == {1: (None, True)}
    assert plan.unidades_a_cargar == 0
    assert plan.no_facturables_a_cargar == 1


# ─── Las secciones del informe ──────────────────────────────────────────────

LINEAS = [
    "Tarea Uno;Grupo A;HORAS PEON",           # a cargar: unidad
    "Tarea Dos;Grupo A;BINS C",               # a cargar: unidad de cosecha
    "Tarea Tres;Grupo B;NO FACTURABLE",       # a cargar: No facturable
    "Tarea Cuatro;Grupo B;",                  # sin grupo
    "Tarea Cinco;Grupo B;TONELADAS",          # grupo desconocido
    "Tarea Vieja;Grupo B;PLANTA",             # no está entre las activas
    "Tarea Doble;Grupo C;HECTAREA",           # dos tareas activas con ese nombre
    "Tarea Seis;Grupo C;PLANTA",              # repetida con grupos distintos
    "tarea  seis;Grupo C;TANCADA",
    "Tarea Siete;Grupo C;VIAJES",             # repetida con el mismo grupo: cuenta una vez
    "TAREA SIETE ;Grupo C;viajes",
    "Tarea Ocho;Grupo D;HORAS TRACTOR",       # ya definida igual
    "Tarea Nueve;Grupo D;HORAS TRACTOR",      # ya definida distinto: el CSV la contradice
]

CAMPO = [
    tarea(1, "TAREA UNO"),
    tarea(2, "TAREA DOS"),
    tarea(3, "TAREA TRES"),
    tarea(4, "TAREA CUATRO"),
    tarea(5, "TAREA CINCO"),
    tarea(6, "TAREA DOBLE"),
    tarea(7, "TAREA  DOBLE"),
    tarea(8, "TAREA SEIS"),
    tarea(9, "TAREA SIETE"),
    tarea(10, "TAREA OCHO"),
    tarea(11, "TAREA NUEVE"),
    tarea(12, "TAREA SIN CSV"),
]

DEFINIDAS = {10: ("horas_tractor", False), 11: (None, True)}


@pytest.fixture()
def plan(tmp_path):
    return planificar(leer_maestro(escribir_csv(tmp_path, LINEAS)), CAMPO, DEFINIDAS)


def test_seccion_a_cargar(plan):
    assert _cargadas(plan) == {
        1: ("horas_peon", False),
        2: ("bins_c", False),
        3: (None, True),
        9: ("viajes", False),
    }
    assert (plan.unidades_a_cargar, plan.no_facturables_a_cargar) == (3, 1)


def test_seccion_sin_grupo(plan):
    assert plan.sin_grupo == ["Tarea Cuatro"]


def test_seccion_grupo_desconocido(plan):
    assert plan.grupo_desconocido == [("Tarea Cinco", "TONELADAS")]


def test_seccion_no_esta_entre_las_activas(plan):
    assert plan.no_activa == ["Tarea Vieja"]


def test_seccion_nombre_ambiguo_en_el_campo(plan):
    assert plan.ambigua_en_campo == [("Tarea Doble", [6, 7])]


def test_seccion_repetida_en_el_csv_con_grupos_distintos(plan):
    assert plan.repetida_en_csv == [("Tarea Seis", ["PLANTA", "TANCADA"])]
    assert 8 not in _cargadas(plan)


def test_seccion_ya_definidas_no_se_tocan_y_se_listan_las_contradichas(plan):
    assert [d["tarea_id"] for d in plan.ya_definidas] == [10, 11]
    assert [d["tarea_id"] for d in plan.contradichas] == [11]
    contradicha = plan.contradichas[0]
    assert contradicha["actual"] == (None, True)
    assert contradicha["csv"] == ("horas_tractor", False)
    assert 10 not in _cargadas(plan) and 11 not in _cargadas(plan)


def test_seccion_activas_que_no_estan_en_el_csv(plan):
    assert plan.faltan_en_csv == [{"tarea_id": 12, "nombre": "TAREA SIN CSV"}]


# ─── Aplicar ────────────────────────────────────────────────────────────────

def test_aplicar_no_toca_lo_que_ya_tiene_fila_y_carga_sin_persona(tmp_path, db):
    db.add_all([
        TareaFacturacion(tarea_id=10, unidad_sugerida="horas_tractor", actualizado_por=7),
        TareaFacturacion(tarea_id=11, no_facturable=True, actualizado_por=7),
    ])
    db.commit()
    plan = planificar(leer_maestro(escribir_csv(tmp_path, LINEAS)), CAMPO, definidas(db))

    assert aplicar(db, plan) == 4

    db.expire_all()
    filas = {f.tarea_id: f for f in db.query(TareaFacturacion).all()}
    assert set(filas) == {1, 2, 3, 9, 10, 11}
    for tarea_id in (1, 2, 3, 9):
        assert filas[tarea_id].actualizado_por is None
        assert filas[tarea_id].actualizado_en is not None
    assert (filas[2].unidad_sugerida, filas[2].no_facturable) == ("bins_c", False)
    assert (filas[3].unidad_sugerida, filas[3].no_facturable) == (None, True)
    # Las que ya estaban, como estaban.
    assert (filas[11].unidad_sugerida, filas[11].no_facturable, filas[11].actualizado_por) == (None, True, 7)
    assert filas[10].actualizado_por == 7


def test_planificar_de_nuevo_despues_de_aplicar_da_cero(tmp_path, db):
    filas = leer_maestro(escribir_csv(tmp_path, LINEAS))
    aplicar(db, planificar(filas, CAMPO, definidas(db)))

    otra_vez = planificar(filas, CAMPO, definidas(db))

    assert otra_vez.a_cargar == []
    assert aplicar(db, otra_vez) == 0
