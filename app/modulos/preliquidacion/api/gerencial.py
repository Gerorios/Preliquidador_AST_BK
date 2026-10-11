from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_propia, get_db_externa, get_db_sueldos
from app.modulos.preliquidacion.permisos import ver_gerencial, ver_quincenas_gerencial
from app.modulos.preliquidacion.models import Preliquidacion
from app.modulos.preliquidacion.services.consulta_externa import ConsultaExternaService
from app.modulos.preliquidacion.services.preliquidacion_service import PreliquidacionService
from app.modulos.preliquidacion.services.gerencial_service import (
    GerencialService, PeriodoInvalidoError, UMBRAL_DESVIO_DEFAULT,
)

# Vista gerencial: sólo lectura, con Ver en la pantalla `gerencial` (ADR-0020).
# Cada endpoint declara su permiso; `/quincenas` lo ve también quien tiene
# Conceptos, que lo usa de selector cuando no ve las pantallas del listado.
router = APIRouter(
    prefix="/api/gerencial",
    tags=["Gerencial"],
)


def get_service(db_propia: Session = Depends(get_db_propia)) -> GerencialService:
    return GerencialService(db_propia)


def _atrapar_periodo(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PeriodoInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quincenas", dependencies=[Depends(ver_quincenas_gerencial)])
def quincenas_disponibles(service: GerencialService = Depends(get_service)):
    """Quincenas con preliquidación, para el selector de período."""
    return [str(q) for q in service.quincenas_disponibles()]


@router.get("/empresas", dependencies=[Depends(ver_gerencial)])
def empresas_disponibles(service: GerencialService = Depends(get_service)):
    """Empresas con líneas preliquidadas, para el filtro."""
    return service.empresas_disponibles()


@router.get("/resumen", dependencies=[Depends(ver_gerencial)])
def resumen(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None, description="Mes calendario YYYY-MM"),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """Mano de obra total del período, con comparación contra el anterior."""
    return _atrapar_periodo(service.resumen, quincena, mes, empresa)


@router.get("/evolucion", dependencies=[Depends(ver_gerencial)])
def evolucion(
    empresa: Optional[str] = Query(None),
    limite: int = Query(24, ge=1, le=120),
    service: GerencialService = Depends(get_service),
):
    """Serie de mano de obra por quincena (ascendente), para el gráfico."""
    return service.evolucion(empresa, limite)


@router.get("/por-cliente", dependencies=[Depends(ver_gerencial)])
def por_cliente(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """Ranking de gasto por cliente del período."""
    return _atrapar_periodo(service.por_cliente, quincena, mes, empresa)


@router.get("/por-grupo-tarea", dependencies=[Depends(ver_gerencial)])
def por_grupo_tarea(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    grupo: Optional[str] = Query(None, description="Drill: tareas de este grupo"),
    service: GerencialService = Depends(get_service),
    db_externa: Session = Depends(get_db_externa),
):
    """Desglose por grupo_tarea del catálogo; con `grupo`, drill a tareas."""
    catalogo = ConsultaExternaService(db_externa).obtener_tareas()
    grupos = {t["nombre"]: (t["grupo_tarea"] or "SIN GRUPO") for t in catalogo}
    return _atrapar_periodo(
        service.por_grupo_tarea, quincena, mes, empresa, grupos, grupo
    )


@router.get("/desvios-persona", dependencies=[Depends(ver_gerencial)])
def desvios_persona(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    umbral: float = Query(UMBRAL_DESVIO_DEFAULT, ge=0, le=500),
    service: GerencialService = Depends(get_service),
):
    """Personas vs. su propia media histórica (6 quincenas, mínimo 3)."""
    return _atrapar_periodo(service.desvios_por_persona, quincena, mes, empresa, umbral)


@router.get("/indicadores", dependencies=[Depends(ver_gerencial)])
def indicadores(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """KPIs de control: $/hora jornal y descomposición de la variación
    (dotación / actividad / precio) contra el período anterior."""
    return _atrapar_periodo(service.indicadores, quincena, mes, empresa)


@router.get("/desvios-cliente", dependencies=[Depends(ver_gerencial)])
def desvios_cliente(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    umbral: float = Query(UMBRAL_DESVIO_DEFAULT, ge=0, le=500),
    service: GerencialService = Depends(get_service),
):
    """Clientes vs. su propia media histórica (6 quincenas, mínimo 3)."""
    return _atrapar_periodo(service.desvios_por_cliente, quincena, mes, empresa, umbral)


# ─── Controles de pago (solo lectura) ────────────────────────────────────────
#
# Los controles Plantas/Tancadas vs Jornal viven en Verificación para el
# liquidador (que además carga el valor hora). Acá se exponen los MISMOS
# cálculos por quincena para el gerente, sin la escritura: si el valor hora
# no está cargado, la respuesta lo trae en null y el front lo avisa.

def _control_por_quincena(
    metodo: str,
    quincena: date,
    db_propia: Session,
    db_externa: Session,
    db_sueldos: Session,
):
    preliq = (
        db_propia.query(Preliquidacion)
        .filter(Preliquidacion.quincena == quincena)
        .first()
    )
    if preliq is None:
        raise HTTPException(
            status_code=400,
            detail=f"No existe preliquidación de la quincena {quincena}",
        )
    service = PreliquidacionService(db_propia, db_externa, db_sueldos)
    try:
        return getattr(service, metodo)(preliq.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/control-plantas", dependencies=[Depends(ver_gerencial)])
def control_plantas(
    quincena: date = Query(...),
    db_propia: Session = Depends(get_db_propia),
    db_externa: Session = Depends(get_db_externa),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Control Plantas vs Jornal de la quincena (lectura)."""
    return _control_por_quincena(
        "control_plantas_jornal", quincena, db_propia, db_externa, db_sueldos
    )


@router.get("/control-tancadas", dependencies=[Depends(ver_gerencial)])
def control_tancadas(
    quincena: date = Query(...),
    db_propia: Session = Depends(get_db_propia),
    db_externa: Session = Depends(get_db_externa),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Control Tancadas vs Jornal de la quincena (lectura)."""
    return _control_por_quincena(
        "control_tancadas_jornal", quincena, db_propia, db_externa, db_sueldos
    )
