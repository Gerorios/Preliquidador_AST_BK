from decimal import Decimal
from types import SimpleNamespace

from app.services.motor_reglas import MotorReglas
from app.services.preliquidacion_service import PreliquidacionService


def _svc():
    # Instancia sin __init__ (no toca DB); solo necesita self.motor
    svc = PreliquidacionService.__new__(PreliquidacionService)
    svc.motor = MotorReglas(None)
    return svc


def _linea(**kw):
    base = dict(id=1, hsjornal=Decimal("8"), hsmaquina=Decimal("0"),
                tancadas=Decimal("0"), unidades=Decimal("0"))
    base.update(kw)
    return SimpleNamespace(**base)


def _regla(precio, unidad_base="hsjornal", codigo=100, tipo="REMUNERATIVO"):
    return SimpleNamespace(precio=precio, unidad_base=unidad_base, codigo=codigo, tipo=tipo)


def test_concepto_sin_precio_no_genera_fila():
    svc = _svc()
    conceptos = svc._generar_conceptos_automaticos(_linea(), [_regla(precio=None)])
    assert conceptos == []


def test_concepto_con_precio_genera_importe():
    svc = _svc()
    linea = _linea(hsjornal=Decimal("8"))
    conceptos = svc._generar_conceptos_automaticos(linea, [_regla(precio=Decimal("1000"), unidad_base="hsjornal")])
    assert len(conceptos) == 1
    assert conceptos[0].importe == Decimal("8000.00")  # 8 hs * 1000


def test_mix_solo_genera_los_que_tienen_precio():
    svc = _svc()
    reglas = [_regla(precio=None, codigo=1), _regla(precio=Decimal("500"), unidad_base="tancadas", codigo=2)]
    linea = _linea(tancadas=Decimal("3"))
    conceptos = svc._generar_conceptos_automaticos(linea, reglas)
    assert len(conceptos) == 1
    assert conceptos[0].codigo_concepto == 2
    assert conceptos[0].importe == Decimal("1500.00")  # 3 tancadas * 500
