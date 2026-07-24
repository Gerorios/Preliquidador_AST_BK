from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_propia, get_db_externa
from app.api.auth import requiere_rol
from app.services.consulta_externa import ConsultaExternaService
from app.services.gerencial_service import (
    GerencialService, PeriodoInvalidoError, UMBRAL_DESVIO_DEFAULT,
)

# Vista gerencial: solo lectura, accesible a todos los roles (es el ÚNICO
# lugar, junto con los GET del maestro de precios, al que llega el gerente).
router = APIRouter(
    prefix="/api/gerencial",
    tags=["Gerencial"],
    dependencies=[Depends(requiere_rol("admin", "jefe", "gerente"))],
)


def get_service(db_propia: Session = Depends(get_db_propia)) -> GerencialService:
    return GerencialService(db_propia)


def _atrapar_periodo(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PeriodoInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quincenas")
def quincenas_disponibles(service: GerencialService = Depends(get_service)):
    """Quincenas con preliquidación, para el selector de período."""
    return [str(q) for q in service.quincenas_disponibles()]


@router.get("/empresas")
def empresas_disponibles(service: GerencialService = Depends(get_service)):
    """Empresas con líneas preliquidadas, para el filtro."""
    return service.empresas_disponibles()


@router.get("/resumen")
def resumen(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None, description="Mes calendario YYYY-MM"),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """Mano de obra total del período, con comparación contra el anterior."""
    return _atrapar_periodo(service.resumen, quincena, mes, empresa)


@router.get("/evolucion")
def evolucion(
    empresa: Optional[str] = Query(None),
    limite: int = Query(24, ge=1, le=120),
    service: GerencialService = Depends(get_service),
):
    """Serie de mano de obra por quincena (ascendente), para el gráfico."""
    return service.evolucion(empresa, limite)


@router.get("/por-cliente")
def por_cliente(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """Ranking de gasto por cliente del período."""
    return _atrapar_periodo(service.por_cliente, quincena, mes, empresa)


@router.get("/por-grupo-tarea")
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


@router.get("/desvios-persona")
def desvios_persona(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    umbral: float = Query(UMBRAL_DESVIO_DEFAULT, ge=0, le=500),
    service: GerencialService = Depends(get_service),
):
    """Personas vs. su propia media histórica (6 quincenas, mínimo 3)."""
    return _atrapar_periodo(service.desvios_por_persona, quincena, mes, empresa, umbral)
