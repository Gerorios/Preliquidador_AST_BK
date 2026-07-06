from decimal import Decimal

from app.services.motor_reglas import MotorReglas


def _motor():
    # calcular_cantidad_concepto no toca la DB; alcanza con db=None
    return MotorReglas(None)


def _cant(unidad_base, hsjornal=0, hsmaquina=0, tancadas=0, unidades=0):
    return _motor().calcular_cantidad_concepto(
        unidad_base=unidad_base,
        hsjornal=Decimal(str(hsjornal)),
        hsmaquina=Decimal(str(hsmaquina)),
        tancadas=Decimal(str(tancadas)),
        unidades=Decimal(str(unidades)),
    )


def test_passthrough_por_unidad():
    assert _cant("hsjornal", hsjornal=7) == Decimal("7")
    assert _cant("hsmaquina", hsmaquina=3) == Decimal("3")
    assert _cant("tancadas", tancadas=12) == Decimal("12")
    assert _cant("unidades", unidades=500) == Decimal("500")


def test_fijo_siempre_uno():
    assert _cant("fijo") == Decimal("1")
    assert _cant("fijo", hsjornal=99) == Decimal("1")


def test_unidad_desconocida_es_cero():
    assert _cant("no_existe", hsjornal=8) == Decimal("0")


# ─── Jornal tope 1: 5 horas o más = 1 jornal (borde confirmado en grilling) ────

def test_jornal_tope1_cinco_exactas_paga_uno():
    assert _cant("jornal_tope1", hsjornal=5) == Decimal("1")


def test_jornal_tope1_mas_de_cinco_paga_uno_sin_excedente():
    assert _cant("jornal_tope1", hsjornal=9) == Decimal("1")


def test_jornal_tope1_menos_de_cinco_paga_medio():
    assert _cant("jornal_tope1", hsjornal=4.99) == Decimal("0.5")
    assert _cant("jornal_tope1", hsjornal=0.5) == Decimal("0.5")


def test_jornal_tope1_cero_horas_paga_cero():
    assert _cant("jornal_tope1", hsjornal=0) == Decimal("0")


def test_none_se_trata_como_cero():
    m = _motor()
    assert m.calcular_cantidad_concepto("hsjornal", None, None, None, None) == Decimal("0")
    assert m.calcular_cantidad_concepto("jornal_tope1", None, None, None, None) == Decimal("0")
