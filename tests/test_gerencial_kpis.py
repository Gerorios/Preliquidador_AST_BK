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
           empresa="LA ASTURIANA", cliente="CLIENTE A", tarea="COSECHA LIMON"):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        cuit=cuil, nombre_empleado=nombre, empresa_asignada=empresa,
        nombre_cliente=cliente, nombre_finca="FINCA 1", nombre_tarea=tarea,
        importe_total=Decimal(str(importe)),
    )
    db.add(l)
    db.commit()
    return l


# Quincenas: 1ra = día 1, 2da = día 16
Q_MAY_1 = date(2026, 5, 1)
Q_MAY_2 = date(2026, 5, 16)
Q_JUN_1 = date(2026, 6, 1)
Q_JUN_2 = date(2026, 6, 16)


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

    assert [p["nombre"] for p in r["sin_historial"]] == ["PEDRO"]


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
