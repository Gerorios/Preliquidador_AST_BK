from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Preliquidacion, PreliquidacionLinea
from app.services.gerencial_service import GerencialService, PeriodoInvalidoError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, importe, cuil="20-11111111-1", nombre="JUAN",
           empresa="LA ASTURIANA", cliente="CLIENTE A", tarea="COSECHA LIMON",
           hsjornal=None, importe_base=None):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        cuit=cuil, nombre_empleado=nombre, empresa_asignada=empresa,
        nombre_cliente=cliente, nombre_finca="FINCA 1", nombre_tarea=tarea,
        importe_total=Decimal(str(importe)),
        hsjornal=Decimal(str(hsjornal)) if hsjornal is not None else None,
        importe_base=Decimal(str(importe_base)) if importe_base is not None else None,
    )
    db.add(l)
    db.commit()
    return l


# Quincenas: 1ra = día 1, 2da = día 16
Q_MAY_1 = date(2026, 5, 1)
Q_MAY_2 = date(2026, 5, 16)
Q_JUN_1 = date(2026, 6, 1)
Q_JUN_2 = date(2026, 6, 16)


def test_empresas_disponibles(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 100, empresa="PAMPLONA")
    _linea(db, p, 100, empresa="LA ASTURIANA", cuil="20-2")
    _linea(db, p, 100, empresa=None, cuil="20-3")

    assert GerencialService(db).empresas_disponibles() == ["LA ASTURIANA", "PAMPLONA"]


def test_periodo_exige_quincena_o_mes(db):
    svc = GerencialService(db)
    with pytest.raises(PeriodoInvalidoError):
        svc.resumen(None, None, None)
    with pytest.raises(PeriodoInvalidoError):
        svc.resumen(Q_MAY_1, "2026-05", None)


def test_periodo_inexistente(db):
    _preliq(db, Q_MAY_1)
    svc = GerencialService(db)
    with pytest.raises(PeriodoInvalidoError):
        svc.resumen(Q_JUN_1, None, None)
    with pytest.raises(PeriodoInvalidoError):
        svc.resumen(None, "2026-06", None)


def test_resumen_quincena_y_variacion(db):
    p1 = _preliq(db, Q_MAY_1)
    p2 = _preliq(db, Q_MAY_2)
    _linea(db, p1, 1000)
    _linea(db, p2, 1000, cuil="20-1")
    _linea(db, p2, 500, cuil="20-2")

    r = GerencialService(db).resumen(Q_MAY_2, None, None)
    assert r["total"] == 1500.0
    assert r["personas"] == 2
    assert r["lineas"] == 2
    assert r["periodo_anterior"]["total"] == 1000.0
    assert r["variacion_pct"] == 50.0


def test_resumen_excluye_mensualizados(db):
    """La plata de las personas mensualizadas (sueldo fijo, no jornal) no
    entra a ningún cálculo de mano de obra de Gerencial."""
    from app.services.preliquidacion_service import EMPLEADOS_MENSUALIZADOS
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 1000, cuil="20-1", nombre="OTRO")
    _linea(db, p, 5000, cuil="20-2", nombre=EMPLEADOS_MENSUALIZADOS[0])

    r = GerencialService(db).resumen(Q_MAY_1, None, None)
    assert r["total"] == 1000.0
    assert r["personas"] == 1


def test_resumen_mes_agrupa_sus_quincenas_y_compara_mes_anterior(db):
    pm1 = _preliq(db, Q_MAY_1)
    pm2 = _preliq(db, Q_MAY_2)
    pj1 = _preliq(db, Q_JUN_1)
    pj2 = _preliq(db, Q_JUN_2)
    _linea(db, pm1, 400)
    _linea(db, pm2, 600)
    _linea(db, pj1, 800)
    _linea(db, pj2, 700)

    r = GerencialService(db).resumen(None, "2026-06", None)
    assert r["total"] == 1500.0
    assert sorted(r["quincenas"]) == [str(Q_JUN_1), str(Q_JUN_2)]
    # mes anterior completo (las 2 quincenas de mayo)
    assert r["periodo_anterior"]["total"] == 1000.0
    assert r["variacion_pct"] == 50.0


def test_resumen_filtra_por_empresa(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 1000, empresa="LA ASTURIANA")
    _linea(db, p, 300, empresa="PAMPLONA", cuil="20-2")

    r = GerencialService(db).resumen(Q_MAY_1, None, "PAMPLONA")
    assert r["total"] == 300.0
    assert r["personas"] == 1


def test_evolucion_orden_ascendente(db):
    _linea(db, _preliq(db, Q_MAY_2), 200)
    _linea(db, _preliq(db, Q_MAY_1), 100)

    serie = GerencialService(db).evolucion(None)
    assert [s["quincena"] for s in serie] == [str(Q_MAY_1), str(Q_MAY_2)]
    assert [s["total"] for s in serie] == [100.0, 200.0]


def test_por_cliente_ranking_y_porcentaje(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 750, cliente="SAN MIGUEL")
    _linea(db, p, 250, cliente="CITROMAX")

    r = GerencialService(db).por_cliente(Q_MAY_1, None, None)
    assert [c["cliente"] for c in r] == ["SAN MIGUEL", "CITROMAX"]
    assert r[0]["porcentaje"] == 75.0
    assert r[1]["porcentaje"] == 25.0


def test_por_grupo_tarea_agrupa_con_catalogo_y_drill(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 100, tarea="COSECHA LIMON")
    _linea(db, p, 200, tarea="COSECHA PALTA")
    _linea(db, p, 300, tarea="PULVERIZACION MECANICA")
    _linea(db, p, 50, tarea="TAREA VIEJA BORRADA")  # ya no está en el catálogo

    grupos = {
        "COSECHA LIMON": "COSECHA",
        "COSECHA PALTA": "COSECHA",
        "PULVERIZACION MECANICA": "PULVERIZACION",
    }
    svc = GerencialService(db)

    r = svc.por_grupo_tarea(Q_MAY_1, None, None, grupos)
    por_grupo = {g["grupo"]: g for g in r}
    assert por_grupo["PULVERIZACION"]["total"] == 300.0
    assert por_grupo["COSECHA"]["total"] == 300.0
    assert por_grupo["COSECHA"]["tareas"] == 2
    assert por_grupo["SIN GRUPO"]["total"] == 50.0

    drill = svc.por_grupo_tarea(Q_MAY_1, None, None, grupos, grupo="COSECHA")
    assert [t["tarea"] for t in drill] == ["COSECHA PALTA", "COSECHA LIMON"]


def test_desvios_persona_contra_su_media(db):
    # Historia de JUAN: 6 quincenas cobrando 1000 → media 1000
    quincenas = [date(2026, 2, 1), date(2026, 2, 16), date(2026, 3, 1),
                 date(2026, 3, 16), date(2026, 4, 1), date(2026, 4, 16)]
    for q in quincenas:
        _linea(db, _preliq(db, q), 1000)
    # Quincena actual: cobra 1400 → +40%
    p_actual = _preliq(db, Q_MAY_1)
    _linea(db, p_actual, 1400)
    # PEDRO: solo 1 quincena de historia → sin historial comparable
    _linea(db, p_actual, 500, cuil="20-2", nombre="PEDRO")
    db.query(PreliquidacionLinea).filter_by(cuit="20-2").first()
    _linea(db, db.query(Preliquidacion).filter_by(quincena=date(2026, 4, 16)).one(),
           480, cuil="20-2", nombre="PEDRO")

    r = GerencialService(db).desvios_por_persona(Q_MAY_1, None, None, umbral_pct=30.0)

    juan = next(p for p in r["personas"] if p["nombre"] == "JUAN")
    assert juan["media_historica"] == 1000.0
    assert juan["desvio_pct"] == 40.0
    assert juan["supera_umbral"] is True
    assert juan["quincenas_historia"] == 6
    assert set(juan.keys()) == {
        "cuil", "nombre", "promedio_quincenal", "quincenas_historia",
        "media_historica", "desvio_pct", "supera_umbral",
    }
    assert [p["nombre"] for p in r["sin_historial"]] == ["PEDRO"]


def test_desvios_persona_excluye_mensualizados(db):
    from app.services.preliquidacion_service import EMPLEADOS_MENSUALIZADOS
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 1000, cuil="20-1", nombre="JUAN")
    _linea(db, p, 9000, cuil="20-2", nombre=EMPLEADOS_MENSUALIZADOS[0])

    r = GerencialService(db).desvios_por_persona(Q_MAY_1, None, None)

    nombres = {p["nombre"] for p in r["personas"] + r["sin_historial"]}
    assert EMPLEADOS_MENSUALIZADOS[0] not in nombres


def test_desvios_ventana_limita_a_6_quincenas(db):
    # 8 quincenas de historia: las 2 más viejas con importes enormes que
    # deben quedar FUERA de la ventana de 6
    viejas = [date(2025, 11, 1), date(2025, 11, 16)]
    for q in viejas:
        _linea(db, _preliq(db, q), 99999)
    recientes = [date(2026, 2, 1), date(2026, 2, 16), date(2026, 3, 1),
                 date(2026, 3, 16), date(2026, 4, 1), date(2026, 4, 16)]
    for q in recientes:
        _linea(db, _preliq(db, q), 1000)
    _linea(db, _preliq(db, Q_MAY_1), 1000)

    r = GerencialService(db).desvios_por_persona(Q_MAY_1, None, None)
    juan = r["personas"][0]
    assert juan["media_historica"] == 1000.0
    assert juan["desvio_pct"] == 0.0
    assert juan["supera_umbral"] is False


def test_desvios_mes_usa_promedio_quincenal(db):
    # Historia: 3 quincenas de 1000. Mes actual: 2 quincenas de 1200 c/u.
    # El desvío compara el PROMEDIO quincenal (1200) vs la media (1000) → +20%,
    # no el total del mes (2400) vs la media quincenal.
    for q in [date(2026, 4, 1), date(2026, 4, 16), date(2026, 3, 16)]:
        _linea(db, _preliq(db, q), 1000)
    _linea(db, _preliq(db, Q_MAY_1), 1200)
    _linea(db, _preliq(db, Q_MAY_2), 1200)

    r = GerencialService(db).desvios_por_persona(None, "2026-05", None)
    assert r["personas"][0]["desvio_pct"] == 20.0


# ─── Indicadores de control ──────────────────────────────────────────────────

def test_indicadores_metricas_del_periodo(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 1000, hsjornal=10)
    _linea(db, p, 200, cuil="20-2", hsjornal=None)

    r = GerencialService(db).indicadores(Q_MAY_1, None, None)
    a = r["actual"]
    assert a["total"] == 1200.0
    assert a["horas_jornal"] == 10.0
    assert a["costo_hora"] == 120.0          # 1200 / 10
    assert r["anterior"] is None
    assert r["variaciones"] is None
    assert r["descomposicion"] is None


def test_indicadores_sin_horas_costo_hora_none(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 500)  # sin hsjornal
    r = GerencialService(db).indicadores(Q_MAY_1, None, None)
    assert r["actual"]["horas_jornal"] == 0.0
    assert r["actual"]["costo_hora"] is None


def test_indicadores_descomposicion_suma_exacta(db):
    # Anterior: 2 personas × 10 hs × $100/h = 2000
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 1000, cuil="20-1", hsjornal=10, importe_base=1000)
    _linea(db, p0, 1000, cuil="20-2", hsjornal=10, importe_base=1000)
    # Actual: 3 personas × 12 hs × $110/h = 3960
    p1 = _preliq(db, Q_MAY_2)
    for c in ("20-1", "20-2", "20-3"):
        _linea(db, p1, 1320, cuil=c, hsjornal=12, importe_base=1320)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    d = r["descomposicion"]
    assert d["dotacion"]["monto"] == 1000.0    # (3-2) × 10 × 100
    assert d["actividad"]["monto"] == 600.0    # (36 - 30) × 100
    assert d["precio"]["monto"] == 360.0       # 3960 - 3600
    # suma exacta de la variación
    assert d["dotacion"]["monto"] + d["actividad"]["monto"] + d["precio"]["monto"] == 1960.0
    assert d["dotacion"]["pct"] == 50.0
    assert d["actividad"]["pct"] == 30.0
    assert d["precio"]["pct"] == 18.0
    v = r["variaciones"]
    assert v["total_pct"] == 98.0
    assert v["costo_hora_pct"] == 10.0         # 110 vs 100


def test_indicadores_descomposicion_none_sin_horas_previas(db):
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 1000)                        # sin horas en el período anterior
    p1 = _preliq(db, Q_MAY_2)
    _linea(db, p1, 1200, hsjornal=10, importe_base=1200)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    assert r["anterior"] is not None
    assert r["descomposicion"] is None          # H0 == 0 → no explicable
    assert r["variaciones"]["total_pct"] == 20.0
    assert r["variaciones"]["costo_hora_pct"] is None


def test_indicadores_descomposicion_suma_exacta_con_decimales(db):
    # Valores no enteros: hpp0 y cph0 no terminan, así que redondear cada
    # componente por separado desalinearía la suma contra round(t1-t0, 2).
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 244.44, cuil="20-1", hsjornal="4.10", importe_base=244.44)
    _linea(db, p0, 244.44, cuil="20-2", hsjornal="3.30", importe_base=244.44)
    _linea(db, p0, 244.45, cuil="20-3", hsjornal="2.60", importe_base=244.45)

    p1 = _preliq(db, Q_MAY_2)
    _linea(db, p1, 111.11, cuil="20-1", hsjornal="2.20", importe_base=111.11)
    _linea(db, p1, 111.11, cuil="20-2", hsjornal="1.90", importe_base=111.11)
    _linea(db, p1, 111.11, cuil="20-3", hsjornal="1.70", importe_base=111.11)
    _linea(db, p1, 111.12, cuil="20-4", hsjornal="2.05", importe_base=111.12)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    d = r["descomposicion"]
    t0, t1 = r["anterior"]["total"], r["actual"]["total"]
    suma = d["dotacion"]["monto"] + d["actividad"]["monto"] + d["precio"]["monto"]
    assert suma == round(t1 - t0, 2)


def test_indicadores_costo_hora_pct_con_costo_hora_actual_cero(db):
    # Actual: importe total 0 pero con horas cargadas → costo_hora == 0.0
    # (legítimo, no ausente). El chequeo debe distinguirlo de "sin dato".
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 1000, hsjornal=10, importe_base=1000)
    p1 = _preliq(db, Q_MAY_2)
    _linea(db, p1, 0, hsjornal=10, importe_base=0)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    assert r["actual"]["costo_hora"] == 0.0
    assert r["variaciones"]["costo_hora_pct"] == -100.0


# ─── Desvíos por cliente ─────────────────────────────────────────────────────

def test_desvios_cliente_contra_su_media(db):
    # Historia del CLIENTE A: 3 quincenas a 1000
    for q in (date(2026, 4, 1), date(2026, 4, 16), Q_MAY_1):
        _linea(db, _preliq(db, q), 1000, cliente="CLIENTE A")
    # Período actual: CLIENTE A gasta 1500 (+50%), CLIENTE B aparece nuevo
    p = _preliq(db, Q_MAY_2)
    _linea(db, p, 1500, cliente="CLIENTE A")
    _linea(db, p, 800, cuil="20-2", cliente="CLIENTE B")

    r = GerencialService(db).desvios_por_cliente(Q_MAY_2, None, None, umbral_pct=30.0)
    a = next(c for c in r["clientes"] if c["cliente"] == "CLIENTE A")
    assert a["promedio_quincenal"] == 1500.0
    assert a["media_historica"] == 1000.0
    assert a["desvio_pct"] == 50.0
    assert a["supera_umbral"] is True
    assert set(a.keys()) == {
        "cliente", "promedio_quincenal", "quincenas_historia",
        "media_historica", "desvio_pct", "supera_umbral",
    }
    nuevos = [c["cliente"] for c in r["sin_historial"]]
    assert "CLIENTE B" in nuevos


def test_desvios_cliente_sin_cliente_agrupa(db):
    for q in (date(2026, 4, 1), date(2026, 4, 16), Q_MAY_1):
        _linea(db, _preliq(db, q), 500, cliente=None)
    p = _preliq(db, Q_MAY_2)
    _linea(db, p, 500, cliente=None)

    r = GerencialService(db).desvios_por_cliente(Q_MAY_2, None, None)
    assert [c["cliente"] for c in r["clientes"]] == ["SIN CLIENTE"]
    assert r["clientes"][0]["desvio_pct"] == 0.0
