from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modulos.preliquidacion.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    ConceptoAdicional, UnidadBaseConcepto, TipoConcepto,
)
from app.modulos.preliquidacion.config import config
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService

# CUIL ficticio: la lista real de mensualizados vive sólo en el .env del
# servidor (el repo es público).
CUIL_MENSUALIZADO = "20111111119"


@pytest.fixture()
def mensualizado(monkeypatch):
    monkeypatch.setattr(config, "empleados_mensualizados_cuil", CUIL_MENSUALIZADO)
    return CUIL_MENSUALIZADO


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=date(2026, 5, 1), valor_hora_pulv=None):
    p = Preliquidacion(quincena=quincena, creado_por=1, valor_hora_pulv=valor_hora_pulv)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente, finca, tancadas, hsjornal, hsmaquina, nombre_empleado=None,
           cuit=None):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        tancadas=Decimal(tancadas), hsjornal=Decimal(hsjornal),
        # hsmaquina es nullable en el modelo: None se guarda como null.
        hsmaquina=Decimal(hsmaquina) if hsmaquina is not None else None,
        unidades=Decimal("0"), importe_total=Decimal("0"), linea_incompleta=False,
        nombre_empleado=nombre_empleado, cuit=cuit,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("1")):
    """Adjunta a la línea un concepto aplicado con unidad_base = tancadas, que
    es lo que la marca como 'se paga por tancada' para el control."""
    c = ConceptoAdicional(
        linea_id=linea.id, descripcion="Tancada", tipo=TipoConcepto.OTRO,
        unidad_base="tancadas", precio=precio, cantidad=cantidad,
        importe=(cantidad * precio), ingresado_por=1,
    )
    db.add(c)
    db.commit()
    return c


def _concepto_maestro_tancada(db, quincena, tarea, cliente=None, finca=None,
                              precio=Decimal("1000"), codigo=1):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=UnidadBaseConcepto.TANCADAS, precio=precio,
        tipo=TipoConcepto.OTRO,
    )
    db.add(c)
    db.commit()
    return c


CAMPOS_VIEJOS = ("valor_jornal", "valor_tancada", "diff")


def test_ejemplo_planilla_valor_hora_maquina_vs_referencia(db):
    """El ejemplo de la planilla del liquidador (ADR-0017): 4 líneas del mismo
    (cliente, finca, tarea), Σ hs jornal 54, Σ hs máquina 34, Σ tancadas 60 a
    4463. Importe pagado 267.780; valor hora pagado por hs máquina
    267.780 / 34 = 7.875,88; referencia 7352 × 1,3 = 9.557,60; variación
    (7.875,88 − 9.557,60) / 9.557,60 ≈ −17,6 %. Ningún ÷2."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("7352"))
    for hsjornal, hsmaquina in (("14", "9"), ("14", "9"), ("13", "8"), ("13", "8")):
        linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                       tancadas="15", hsjornal=hsjornal, hsmaquina=hsmaquina)
        _aplicar_tancada(db, linea, precio=Decimal("4463"), cantidad=Decimal("15"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] == 7352.0
    assert len(res["filas"]) == 1
    fila = res["filas"][0]
    tot = res["totales"]
    for d in (fila, tot):
        assert d["tancadas"] == 60.0
        assert d["hsjornal"] == 54.0
        assert d["hsmaquina"] == 34.0
        assert d["precio"] == 4463.0
        assert d["importe_pagado"] == 267780.0
        assert d["valor_hora_maquina"] == 7875.88
        assert d["valor_hora_referencia"] == 9557.6
        assert d["variacion"] == pytest.approx(-0.176, abs=1e-4)
        for campo in CAMPOS_VIEJOS:
            assert campo not in d
    assert fila["sin_hs_maquina"] is False
    assert tot["filas_sin_hs_maquina"] == 0


def test_control_tancadas_calcula_valores_y_diff(db):
    preliq = _preliq(db, valor_hora_pulv=Decimal("5458.34"))
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="10", hsmaquina="5")
    # precio del pago real: importe/cantidad = 40000/40 = 1000
    _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("40"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] == 5458.34
    assert len(res["filas"]) == 1
    fila = res["filas"][0]
    # columnas crudas (sin /2): tal cual la suma
    assert fila["tancadas"] == 40.0
    assert fila["hsjornal"] == 10.0
    assert fila["hsmaquina"] == 5.0
    # precio del pago real: Σimporte/Σcantidad = 40000/40 = 1000
    assert fila["precio"] == 1000.0
    # importe pagado real, sin ÷2
    assert fila["importe_pagado"] == 40000.0
    # valor hora pagado por hs máquina = 40000 / 5 = 8000
    assert fila["valor_hora_maquina"] == 8000.0
    # referencia = 5458.34 × 1,3 = 7095.842
    assert fila["valor_hora_referencia"] == 7095.84
    # variación = (8000 − 7095.842) / 7095.842 ≈ +0.1274 (la tancada salió
    # más cara que la referencia: positiva)
    assert fila["variacion"] == pytest.approx(0.1274, abs=1e-4)
    assert fila["sin_hs_maquina"] is False

    # totales recalculados sobre las sumas (misma cuenta, una sola fila)
    tot = res["totales"]
    assert tot["importe_pagado"] == 40000.0
    assert tot["valor_hora_maquina"] == 8000.0
    assert tot["valor_hora_referencia"] == 7095.84
    assert tot["variacion"] == pytest.approx(0.1274, abs=1e-4)
    assert tot["filas_sin_hs_maquina"] == 0
    for campo in CAMPOS_VIEJOS:
        assert campo not in fila
        assert campo not in tot


def test_sin_valor_hora_pulv_devuelve_null_no_error(db):
    preliq = _preliq(db, valor_hora_pulv=None)
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="10", hsmaquina="5")
    _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("40"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] is None
    fila = res["filas"][0]
    # sin valor hora no hay referencia contra qué comparar → null (no 0, no error)
    assert fila["valor_hora_referencia"] is None
    assert fila["variacion"] is None
    # lo que sí se puede calcular sigue estando: importe y valor hora pagado
    # (40000 / 5 = 8000), en la fila y en totales
    tot = res["totales"]
    for d in (fila, tot):
        assert d["importe_pagado"] == 40000.0
        assert d["valor_hora_maquina"] == 8000.0
    assert tot["valor_hora_referencia"] is None
    assert tot["variacion"] is None


def test_valor_hora_pulv_cero_deja_variacion_en_null(db):
    """Valor hora cargado en 0: la referencia es 0.0 (es un dato cargado, no
    falta), pero no hay contra qué dividir → variación null, sin
    ZeroDivisionError (ADR-0017)."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("0"))
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="10", hsmaquina="5")
    _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("40"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["valor_hora_pulv"] == 0.0
    fila = res["filas"][0]
    tot = res["totales"]
    for d in (fila, tot):
        assert d["valor_hora_referencia"] == 0.0
        assert d["variacion"] is None
        # el valor hora pagado sí se calcula: 40000 / 5
        assert d["valor_hora_maquina"] == 8000.0


def test_hsjornal_cero_no_anula_la_variacion(db):
    """Las hs de jornal se muestran como dato pero no entran en la cuenta
    (ADR-0017): en 0 no dejan la variación en null."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("5458.34"))
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="40", hsjornal="0", hsmaquina="5")
    _aplicar_tancada(db, linea, precio=Decimal("1000"), cantidad=Decimal("40"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    fila = res["filas"][0]
    assert fila["hsjornal"] == 0.0
    assert fila["variacion"] == pytest.approx(0.1274, abs=1e-4)


@pytest.mark.parametrize("hsmaquina_b", ["0", None], ids=["hsmaquina_cero", "hsmaquina_null"])
def test_fila_sin_hs_maquina_no_entra_en_la_variacion(db, hsmaquina_b):
    """Una fila sin hs máquina (0 o null) se muestra con sus datos crudos, sin
    valor hora pagado ni variación, marcada `sin_hs_maquina`. El total suma
    tancadas, horas e importe de todas las filas, pero el valor hora y la
    variación sólo usan las filas con hs máquina > 0 (ADR-0017)."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("5000"))   # referencia 6500
    # Fila A: hs máquina 10, importe 100000 → valor hora 10000
    la = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                tancadas="50", hsjornal="12", hsmaquina="10")
    _aplicar_tancada(db, la, precio=Decimal("2000"), cantidad=Decimal("50"))
    # Fila B: sin hs máquina, importe 20000
    lb = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 2",
                tancadas="20", hsjornal="6", hsmaquina=hsmaquina_b)
    _aplicar_tancada(db, lb, precio=Decimal("1000"), cantidad=Decimal("20"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert len(res["filas"]) == 2
    fila_a = next(f for f in res["filas"] if f["nombre_finca"] == "FINCA 1")
    fila_b = next(f for f in res["filas"] if f["nombre_finca"] == "FINCA 2")

    assert fila_a["sin_hs_maquina"] is False
    assert fila_a["valor_hora_maquina"] == 10000.0

    # B: datos crudos presentes
    assert fila_b["tancadas"] == 20.0
    assert fila_b["hsjornal"] == 6.0
    assert fila_b["hsmaquina"] == 0.0
    assert fila_b["precio"] == 1000.0
    assert fila_b["importe_pagado"] == 20000.0
    # ...pero sin valor hora pagado ni variación
    assert fila_b["valor_hora_maquina"] is None
    assert fila_b["variacion"] is None
    assert fila_b["sin_hs_maquina"] is True
    # la referencia se repite igual en todas las filas
    assert fila_b["valor_hora_referencia"] == 6500.0

    tot = res["totales"]
    # importe sobre todas las filas
    assert tot["importe_pagado"] == 120000.0
    assert tot["hsmaquina"] == 10.0
    # valor hora y variación sólo con las filas con hs máquina: 100000 / 10
    assert tot["valor_hora_maquina"] == 10000.0
    assert tot["valor_hora_referencia"] == 6500.0
    assert tot["variacion"] == pytest.approx((10000 - 6500) / 6500, abs=1e-4)
    assert tot["filas_sin_hs_maquina"] == 1


def test_solo_incluye_lineas_pagadas_por_tancada(db):
    preliq = _preliq(db, valor_hora_pulv=Decimal("100"))
    # línea pagada por tancada (entra)
    l1 = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                tancadas="10", hsjornal="8", hsmaquina="4")
    _aplicar_tancada(db, l1, precio=Decimal("1000"), cantidad=Decimal("10"))
    # línea sin concepto de tancada (NO entra)
    l2 = _linea(db, preliq, "OTRA", "CLIENTE B", "FINCA 2",
                tancadas="99", hsjornal="8", hsmaquina="4")
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert len(res["filas"]) == 1
    assert res["filas"][0]["nombre_tarea"] == "PULV"


def test_excluye_lineas_de_empleados_mensualizados(db, mensualizado):
    """Las líneas de personas mensualizadas (por CUIL, desde la config del
    módulo) no entran a este control."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("100"))
    l1 = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                tancadas="40", hsjornal="10", hsmaquina="5",
                nombre_empleado="EMPLEADO, MENSUALIZADO", cuit=mensualizado)
    _aplicar_tancada(db, l1)
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert res["filas"] == []
    # su pago tampoco entra en el total
    assert res["totales"]["importe_pagado"] == 0.0


def test_linea_sin_cuit_no_se_excluye(db, mensualizado):
    """NOT IN con NULL da NULL en SQL: una línea sin CUIL sigue entrando."""
    preliq = _preliq(db, valor_hora_pulv=Decimal("100"))
    l1 = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                tancadas="40", hsjornal="10", hsmaquina="5", cuit=None)
    _aplicar_tancada(db, l1)
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    assert len(res["filas"]) == 1


def test_precio_viene_del_pago_real_no_del_maestro(db):
    """El precio de la tancada tiene que salir de Σimporte/Σcantidad de los
    conceptos aplicados, ignorando lo que diga el maestro (que puede estar
    desactualizado o no reflejar por-cliente/por-supervisor, ADR-0011)."""
    preliq = _preliq(db, valor_hora_pulv=None)
    linea = _linea(db, preliq, "PULV", "CLIENTE A", "FINCA 1",
                   tancadas="10", hsjornal="8", hsmaquina="4")
    # el pago real fue a 1500, el maestro dice 1000 — debe ganar el pago real
    _aplicar_tancada(db, linea, precio=Decimal("1500"), cantidad=Decimal("10"))
    _concepto_maestro_tancada(db, preliq.quincena, "PULV", "CLIENTE A", "FINCA 1",
                              precio=Decimal("1000"))
    svc = PreliquidacionService(db)

    res = svc.control_tancadas_jornal(preliq.id)

    fila = res["filas"][0]
    assert fila["precio"] == 1500.0
    assert "precio_comun" not in fila
    assert "precio_especial" not in fila
    assert "var_pct" not in fila


# ─── Setter del valor hora ────────────────────────────────────────────────────

def test_set_valor_hora_pulv(db):
    preliq = _preliq(db)
    svc = PreliquidacionService(db)
    actualizada = svc.set_valor_hora_pulv(preliq.id, Decimal("5458.34"))
    assert actualizada.valor_hora_pulv == Decimal("5458.34")
    actualizada = svc.set_valor_hora_pulv(preliq.id, None)   # None limpia
    assert actualizada.valor_hora_pulv is None


def test_set_valor_hora_pulv_preliquidacion_inexistente(db):
    svc = PreliquidacionService(db)
    with pytest.raises(ValueError, match="Preliquidacion 999 no encontrada"):
        svc.set_valor_hora_pulv(999, Decimal("100"))
