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


def _regla(precio, unidad_base="hsjornal", codigo=100, tipo="REMUNERATIVO", id=1):
    return SimpleNamespace(precio=precio, unidad_base=unidad_base, codigo=codigo, tipo=tipo, id=id)


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


def test_concepto_guarda_snapshot_de_precio_cantidad_y_origen():
    """Fix de trazabilidad: concepto_adicional debe ser un hecho autocontenido
    (precio y cantidad congelados en el momento del cálculo, más el id de la
    regla del maestro que lo origino), no depender de que concepto_liquidacion
    no haya cambiado despues."""
    svc = _svc()
    linea = _linea(hsjornal=Decimal("8"))
    regla = _regla(precio=Decimal("1000"), unidad_base="hsjornal", codigo=42, id=777)
    conceptos = svc._generar_conceptos_automaticos(linea, [regla])
    assert len(conceptos) == 1
    c = conceptos[0]
    assert c.precio == Decimal("1000")
    assert c.cantidad == Decimal("8")
    assert c.concepto_liquidacion_id == 777
    assert c.importe == Decimal("8000.00")  # cantidad * precio, sigue consistente
