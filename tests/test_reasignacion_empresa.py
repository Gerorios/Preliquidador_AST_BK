from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Preliquidacion, PreliquidacionLinea, AjusteManual
from app.services.preliquidacion_service import PreliquidacionService
from app.services.sueldos_service import SueldosService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _sueldos_con(por_cuil: dict) -> SueldosService:
    """SueldosService con el cache ya poblado a mano (sin BD externa real),
    ejercitando el código de producción de legajos_por_cuil/legajo_por_cuil_y_empresa."""
    s = SueldosService.__new__(SueldosService)
    s._cache_cargado = True
    s._por_legajo = {}
    s._por_legajo_empresa = {}
    s._por_cuil = por_cuil
    return s


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, cuit, nombre_empleado, legajo_campo="0000", empresa_asignada="LA ASTURIANA"):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea="TAREA X", nombre_cliente="CLIENTE A", nombre_finca="FINCA 1",
        cuit=cuit, nombre_empleado=nombre_empleado, legajo_campo=legajo_campo,
        empresa_asignada=empresa_asignada, legajo_asignado=legajo_campo,
        alerta_legajo=True, hsjornal=Decimal("8"),
        tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"),
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _svc(db, por_cuil):
    svc = PreliquidacionService(db)
    svc.sueldos = _sueldos_con(por_cuil)
    return svc


def test_agrupa_por_cuil_y_excluye_sin_cuil(db):
    preliq = _preliq(db)
    l1 = _linea(db, preliq, "20111111111", "PEREZ JUAN")
    l2 = _linea(db, preliq, "20111111111", "PEREZ JUAN")  # misma persona, otro dia
    l3 = _linea(db, preliq, "20222222222", "GOMEZ ANA")
    l4 = _linea(db, preliq, "", "SIN CUIL")

    svc = _svc(db, por_cuil={
        "20111111111": [{"empresa": "LA ASTURIANA", "legajo": "111"}, {"empresa": "PAMPLONA", "legajo": "999"}],
        "20222222222": [{"empresa": "LA ASTURIANA", "legajo": "222"}],
    })

    resultado = svc.legajos_disponibles_por_cuil([l1.id, l2.id, l3.id, l4.id])

    assert resultado["sin_cuil"] == [l4.id]
    grupos = {g["cuil"]: g for g in resultado["grupos"]}
    assert set(grupos["20111111111"]["linea_ids"]) == {l1.id, l2.id}
    assert grupos["20111111111"]["legajos_disponibles"] == [
        {"empresa": "LA ASTURIANA", "legajo": "111"}, {"empresa": "PAMPLONA", "legajo": "999"},
    ]
    assert grupos["20222222222"]["linea_ids"] == [l3.id]


def test_reasignar_empresa_setea_legajo_correcto_y_audita(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "20111111111", "PEREZ JUAN", legajo_campo="111", empresa_asignada="LA ASTURIANA")

    svc = _svc(db, por_cuil={
        "20111111111": [{"empresa": "LA ASTURIANA", "legajo": "111"}, {"empresa": "PAMPLONA", "legajo": "999"}],
    })

    resultado = svc.reasignar_empresa_masivo([linea.id], "PAMPLONA", usuario_id=1, motivo="cambio de campaña")

    assert resultado == {"reasignadas": 1, "sin_legajo_en_empresa": []}
    db.refresh(linea)
    assert linea.empresa_asignada == "PAMPLONA"
    assert linea.legajo_asignado == "999"
    assert linea.alerta_legajo is False

    ajustes = db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).all()
    campos = {a.campo_modificado: a.valor_nuevo for a in ajustes}
    assert campos == {"empresa_asignada": "PAMPLONA", "legajo_asignado": "999"}
    assert all(a.motivo == "cambio de campaña" for a in ajustes)


def test_no_reasigna_si_persona_no_tiene_legajo_en_esa_empresa(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "20111111111", "PEREZ JUAN", legajo_campo="111", empresa_asignada="LA ASTURIANA")

    svc = _svc(db, por_cuil={
        "20111111111": [{"empresa": "LA ASTURIANA", "legajo": "111"}],  # no tiene PAMPLONA
    })

    resultado = svc.reasignar_empresa_masivo([linea.id], "PAMPLONA", usuario_id=1)

    assert resultado == {"reasignadas": 0, "sin_legajo_en_empresa": [linea.id]}
    db.refresh(linea)
    assert linea.empresa_asignada == "LA ASTURIANA"  # sin tocar
    assert db.query(AjusteManual).filter(AjusteManual.linea_id == linea.id).count() == 0


def test_reasignacion_persiste_sola_ningun_recalculo_la_pisa(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "20111111111", "PEREZ JUAN", legajo_campo="111", empresa_asignada="LA ASTURIANA")
    svc = _svc(db, por_cuil={
        "20111111111": [{"empresa": "LA ASTURIANA", "legajo": "111"}, {"empresa": "PAMPLONA", "legajo": "999"}],
    })
    svc.reasignar_empresa_masivo([linea.id], "PAMPLONA", usuario_id=1)

    # El recalculo reactivo (WS2) no toca empresa_asignada/legajo_asignado
    svc.recalcular_por_concepto(
        preliq.quincena,
        actual={"tarea_nombre": "TAREA X", "cliente_nombre": "CLIENTE A", "finca_nombre": "FINCA 1"},
    )

    db.refresh(linea)
    assert linea.empresa_asignada == "PAMPLONA"
    assert linea.legajo_asignado == "999"
