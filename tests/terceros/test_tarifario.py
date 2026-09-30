"""El Tarifario (etapa 6): cargar precios y traerlos de otra quincena."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.terceros.models import TarifaViaje
from app.modulos.terceros.services.tarifario_service import (
    TarifaInvalida, TarifarioService, especificidad,
)

Q = date(2026, 8, 1)
ANTERIOR = date(2026, 7, 16)


@pytest.fixture()
def s():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield TarifarioService(db)
    db.close()


# ─── Cargar ─────────────────────────────────────────────────────────────────

def test_una_tarifa_de_viaje_con_sus_cuatro_dimensiones(s):
    t = s.crear("viajes", Q, {"tercero": "ARANDA, HUGO", "cliente": "SAN MIGUEL",
                              "finca": "CASPINCHANGO", "capataz": "SOSA",
                              "precio": "205000", "tipo_viaje": "LARGO"})
    assert t.precio == Decimal("205000")
    assert t.tipo_viaje == "LARGO"
    assert t.heredada is False


def test_una_dimension_que_no_se_carga_queda_vacia_y_no_en_nulo(s):
    """Con NULL el índice único de MySQL dejaría entrar dos reglas idénticas."""
    t = s.crear("viajes", Q, {"tercero": "ARANDA", "precio": "100"})
    assert t.cliente == "" and t.finca == "" and t.capataz == ""


def test_no_se_puede_cargar_dos_veces_la_misma_combinacion(s):
    s.crear("viajes", Q, {"tercero": "ARANDA", "capataz": "SOSA", "precio": "100"})
    with pytest.raises(TarifaInvalida) as e:
        s.crear("viajes", Q, {"tercero": "ARANDA", "capataz": "SOSA", "precio": "120"})
    assert "ambiguo" in str(e.value)


def test_la_misma_combinacion_en_otra_quincena_si_se_puede(s):
    """El tarifario es por quincena: el precio del mes que viene es otra regla."""
    s.crear("viajes", Q, {"tercero": "ARANDA", "precio": "100"})
    otra = s.crear("viajes", date(2026, 8, 16), {"tercero": "ARANDA", "precio": "120"})
    assert otra.precio == Decimal("120")


@pytest.mark.parametrize("tipo", ["combustible", "reparacion", "seguros"])
def test_los_precios_por_tercero_exigen_el_tercero(tipo, s):
    campo = "importe" if tipo == "seguros" else "precio"
    with pytest.raises(TarifaInvalida) as e:
        s.crear(tipo, Q, {campo: "100", "sujeto": "X", "tipo_seguro": "AUTOMOTOR"})
    assert "tercero" in str(e.value)


def test_el_seguro_exige_a_quien_cubre(s):
    with pytest.raises(TarifaInvalida) as e:
        s.crear("seguros", Q, {"tercero": "BARRIOS", "tipo_seguro": "AUTOMOTOR",
                               "importe": "5000"})
    assert "sujeto" in str(e.value)


def test_el_seguro_de_una_maquina_y_el_de_su_chofer_conviven(s):
    """Son dos pólizas distintas del mismo dueño: el tipo las separa."""
    maquina = s.crear("seguros", Q, {
        "tercero": "BARRIOS", "tipo_seguro": "AUTOMOTOR",
        "sujeto": "MANITOU N°0046", "referencia": "ABC123", "importe": "45000"})
    chofer = s.crear("seguros", Q, {
        "tercero": "BARRIOS", "tipo_seguro": "RELACION_DEPENDENCIA",
        "sujeto": "VERA, EMILIO", "referencia": "20434987351", "importe": "12000"})
    assert maquina.id != chofer.id
    assert len(s.listar("seguros", Q)) == 2


def test_dos_polizas_del_mismo_tipo_sobre_el_mismo_sujeto_no(s):
    datos = {"tercero": "BARRIOS", "tipo_seguro": "AUTOMOTOR", "sujeto": "MANITOU", "importe": "1"}
    s.crear("seguros", Q, datos)
    with pytest.raises(TarifaInvalida):
        s.crear("seguros", Q, dict(datos, importe="2"))


def test_un_tipo_de_seguro_inventado_se_rechaza(s):
    with pytest.raises(TarifaInvalida) as e:
        s.crear("seguros", Q, {"tercero": "A", "tipo_seguro": "GRANIZO",
                               "sujeto": "X", "importe": "1"})
    assert "máquina o a una persona" in str(e.value)


def test_la_referencia_guarda_la_patente_o_el_cuil(s):
    t = s.crear("seguros", Q, {"tercero": "A", "tipo_seguro": "ACCIDENTES_PERSONALES",
                               "sujeto": "ROJAS, ANGEL", "referencia": "20123456789",
                               "importe": "1"})
    assert t.referencia == "20123456789"


def test_un_precio_negativo_se_rechaza(s):
    with pytest.raises(TarifaInvalida) as e:
        s.crear("viajes", Q, {"tercero": "X", "precio": "-1"})
    assert "negativo" in str(e.value)


def test_un_precio_en_cero_se_acepta(s):
    """Cero es una decisión explícita —no se le cobra— y es distinta de no
    tener tarifa, que es lo que deja el hecho afuera del recibo."""
    assert s.crear("viajes", Q, {"tercero": "X", "precio": "0"}).precio == Decimal("0")


def test_la_unidad_base_del_servicio_tiene_que_ser_una_de_las_dos(s):
    with pytest.raises(TarifaInvalida) as e:
        s.crear("servicio", Q, {"tercero": "BARRIOS", "precio": "100",
                                "unidad_base": "hsjornal"})
    assert "hora de máquina o por cantidad" in str(e.value)


@pytest.mark.parametrize("unidad", ["hsmaquina", "unidades"])
def test_las_dos_unidades_base_validas(unidad, s):
    t = s.crear("servicio", Q, {"tercero": "BARRIOS", "precio": "100", "unidad_base": unidad})
    assert t.unidad_base == unidad


def test_un_tipo_de_viaje_inventado_se_rechaza(s):
    with pytest.raises(TarifaInvalida):
        s.crear("viajes", Q, {"tercero": "X", "precio": "1", "tipo_viaje": "MEDIANO"})


def test_un_tarifario_que_no_existe_lo_dice(s):
    with pytest.raises(TarifaInvalida) as e:
        s.listar("peajes", Q)
    assert "peajes" in str(e.value)


# ─── Especificidad ──────────────────────────────────────────────────────────

def test_la_regla_con_mas_dimensiones_es_la_mas_especifica(s):
    general = s.crear("viajes", Q, {"tercero": "ARANDA", "precio": "100"})
    especifica = s.crear("viajes", Q, {"tercero": "ARANDA", "cliente": "SAN MIGUEL",
                                       "finca": "LA BAJADA", "capataz": "SOSA",
                                       "precio": "150"})
    assert especificidad(general) == 1
    assert especificidad(especifica) == 4


def test_el_listado_va_de_la_mas_general_a_la_mas_especifica(s):
    s.crear("viajes", Q, {"tercero": "A", "cliente": "C", "finca": "F", "precio": "3"})
    s.crear("viajes", Q, {"tercero": "A", "precio": "1"})
    s.crear("viajes", Q, {"tercero": "A", "cliente": "C", "precio": "2"})
    assert [especificidad(f) for f in s.listar("viajes", Q)] == [1, 2, 3]


# ─── Editar y confirmar ─────────────────────────────────────────────────────

def test_cambiar_el_precio_confirma_la_regla(s):
    """Si alguien lo tocó, ya no es un precio arrastrado sin mirar."""
    t = s.crear("viajes", Q, {"tercero": "X", "precio": "100"})
    t.heredada = True
    s.db.commit()

    t = s.actualizar("viajes", t.id, {"precio": "120"})

    assert t.precio == Decimal("120") and t.heredada is False


def test_confirmar_deja_el_precio_y_saca_la_marca(s):
    t = s.crear("viajes", Q, {"tercero": "X", "precio": "100"})
    t.heredada = True
    s.db.commit()

    t = s.confirmar("viajes", t.id)

    assert t.precio == Decimal("100") and t.heredada is False


def test_eliminar(s):
    t = s.crear("viajes", Q, {"tercero": "X", "precio": "100"})
    s.eliminar("viajes", t.id)
    assert s.listar("viajes", Q) == []


# ─── Copiar de otra quincena ────────────────────────────────────────────────

def test_copiar_trae_las_reglas_marcadas_como_heredadas(s):
    s.crear("viajes", ANTERIOR, {"tercero": "ARANDA", "capataz": "SOSA", "precio": "205000"})
    s.crear("combustible", ANTERIOR, {"tercero": "ARANDA", "precio": "1100"})

    detalle = s.copiar(ANTERIOR, Q)

    copiadas = s.listar("viajes", Q)
    assert len(copiadas) == 1
    assert copiadas[0].precio == Decimal("205000")
    assert copiadas[0].heredada is True
    assert detalle["viajes"]["copiadas"] == 1


def test_copiar_no_pisa_lo_que_ya_se_cargo_en_el_destino(s):
    """Copiar es traer lo que falta. Si alguien ya pactó el precio nuevo, ese
    precio manda: pisarlo sería perder trabajo hecho."""
    s.crear("viajes", ANTERIOR, {"tercero": "ARANDA", "precio": "100"})
    s.crear("viajes", Q, {"tercero": "ARANDA", "precio": "999"})

    detalle = s.copiar(ANTERIOR, Q)

    quedan = s.listar("viajes", Q)
    assert len(quedan) == 1
    assert quedan[0].precio == Decimal("999")
    assert quedan[0].heredada is False
    assert detalle["viajes"] == {"en_origen": 1, "copiadas": 0, "ya_estaban": 1}


def test_copiar_dos_veces_no_duplica(s):
    s.crear("viajes", ANTERIOR, {"tercero": "ARANDA", "precio": "100"})
    s.copiar(ANTERIOR, Q)
    s.copiar(ANTERIOR, Q)
    assert len(s.listar("viajes", Q)) == 1


def test_copiar_se_puede_limitar_a_un_tarifario(s):
    s.crear("viajes", ANTERIOR, {"tercero": "A", "precio": "1"})
    s.crear("combustible", ANTERIOR, {"tercero": "A", "precio": "2"})

    s.copiar(ANTERIOR, Q, tipos=("viajes",))

    assert len(s.listar("viajes", Q)) == 1
    assert s.listar("combustible", Q) == []


def test_copiar_sobre_la_misma_quincena_se_rechaza(s):
    with pytest.raises(TarifaInvalida):
        s.copiar(Q, Q)


def test_copiar_conserva_la_unidad_base_y_el_tipo_de_viaje(s):
    s.crear("viajes", ANTERIOR, {"tercero": "A", "precio": "1", "tipo_viaje": "CORTO"})
    s.crear("servicio", ANTERIOR, {"tercero": "A", "precio": "2", "unidad_base": "unidades"})

    s.copiar(ANTERIOR, Q)

    assert s.listar("viajes", Q)[0].tipo_viaje == "CORTO"
    assert s.listar("servicio", Q)[0].unidad_base == "unidades"


# ─── El resumen del tablero ─────────────────────────────────────────────────

def test_el_resumen_cuenta_cargadas_y_sin_confirmar(s):
    s.crear("viajes", ANTERIOR, {"tercero": "A", "precio": "1"})
    s.copiar(ANTERIOR, Q)
    s.crear("viajes", Q, {"tercero": "B", "precio": "2"})

    r = s.resumen(Q)

    assert r["viajes"] == {"cargadas": 2, "heredadas": 1}
    assert r["seguros"] == {"cargadas": 0, "heredadas": 0}


# ─── Cargar y tocar de a muchas ─────────────────────────────────────────────
#
# Los endpoints en lote llaman a estos mismos métodos en un for. Lo que se
# prueba acá es que una que falla no se lleve puestas a las demás, que es la
# razón de que el lote no se corte al primer error.

def test_confirmar_le_saca_la_marca_de_heredada_sin_tocar_el_precio(s):
    """Copiar una quincena trae doscientas reglas heredadas. Confirmarlas es
    decir «este precio lo miré», no cambiarlo."""
    s.crear("viajes", ANTERIOR, {"tercero": "ARANDA", "precio": "100"})
    s.copiar(ANTERIOR, Q)
    copiada = s.listar("viajes", Q)[0]
    assert copiada.heredada is True

    confirmada = s.confirmar("viajes", copiada.id)
    assert confirmada.heredada is False
    assert confirmada.precio == Decimal("100")


def test_la_quincena_de_una_tarifa_se_sabe_antes_de_borrarla(s):
    """Hace falta para saber qué recalcular una vez que la regla ya no está."""
    t = s.crear("viajes", Q, {"tercero": "ARANDA", "precio": "100"})
    assert s.quincena_de("viajes", t.id) == Q


def test_una_combinacion_repetida_no_frena_a_las_demas(s):
    """Es lo que hace el endpoint en lote: si de cuarenta y cuatro una ya
    estaba, las otras cuarenta y tres tienen que quedar cargadas igual."""
    s.crear("viajes", Q, {"tercero": "ARANDA", "capataz": "SOSA", "precio": "100"})

    cargadas, rechazadas = 0, []
    for datos in ({"tercero": "ARANDA", "capataz": "SOSA", "precio": "200"},
                  {"tercero": "ARANDA", "capataz": "PERALTA", "precio": "200"},
                  {"tercero": "CORNEJO", "capataz": "PERALTA", "precio": "200"}):
        try:
            s.crear("viajes", Q, datos)
            cargadas += 1
        except TarifaInvalida as e:
            rechazadas.append(str(e))

    assert cargadas == 2
    assert len(rechazadas) == 1 and "ambiguo" in rechazadas[0]
    assert len(s.listar("viajes", Q)) == 3
