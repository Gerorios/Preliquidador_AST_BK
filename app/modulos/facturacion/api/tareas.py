"""Endpoints de la pantalla Unidad de medida por defecto.

Contrato en docs/superpowers/plans/2026-10-11-facturacion-e1.md, 2.5. Los dos
leen el maestro de tareas del campo en cada pedido: el GET para listarlas y el
PATCH para no crear filas de tareas que no existen. Si el campo no responde,
ExternaNoDisponible sigue de largo hasta el handler global de app/main.py, que
la devuelve como 503 con su mensaje.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db_externa, get_db_propia
from app.modulos.facturacion.permisos import editar_unidad, ver_unidad
from app.modulos.facturacion.schemas import DefinirTareaIn, TareaFacturacionOut
from app.modulos.facturacion.services.consulta_externa import ConsultaExternaService
from app.modulos.facturacion.services.unidad_service import (
    DefinicionInvalida, TareaNoEncontrada, UnidadService,
)

# Permisos por pantalla (ADR-0020): cada endpoint declara la suya, y el router
# no tiene dependencia propia. El mapa lo fija tests/facturacion/test_mapa_permisos.py.
router = APIRouter(prefix="/api/facturacion", tags=["Facturación"])


def get_consulta_externa(
    db_externa: Session = Depends(get_db_externa),
) -> ConsultaExternaService:
    return ConsultaExternaService(db_externa)


def get_unidades(
    db_propia: Session = Depends(get_db_propia),
) -> UnidadService:
    return UnidadService(db_propia)


@router.get("/tareas", response_model=list[TareaFacturacionOut],
            dependencies=[Depends(ver_unidad)])
def listar_tareas(
    consulta: ConsultaExternaService = Depends(get_consulta_externa),
    servicio: UnidadService = Depends(get_unidades),
):
    """Las tareas activas del campo, primero las Sin definir y después las
    demás, cada grupo en el orden del campo (por nombre)."""
    return servicio.listar(consulta.obtener_tareas())


@router.patch("/tareas/{tarea_id}", response_model=TareaFacturacionOut)
def definir_tarea(
    tarea_id: int,
    req: DefinirTareaIn,
    usuario=Depends(editar_unidad),
    consulta: ConsultaExternaService = Depends(get_consulta_externa),
    servicio: UnidadService = Depends(get_unidades),
):
    """Deja la tarea con una Unidad sugerida, como No facturable o Sin definir.
    Devuelve el ítem con la misma forma que el GET, para que la pantalla
    actualice su fila sin volver a leer el campo."""
    try:
        return servicio.definir(
            consulta.obtener_tareas(), tarea_id,
            req.unidad_sugerida, req.no_facturable, usuario.id,
        )
    except DefinicionInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TareaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
