from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_propia, get_db_externa, get_db_sueldos
from app.api.auth import get_usuario_actual
from app.services.preliquidacion_service import PreliquidacionService
from app.schemas.schemas import (
    PreliquidacionGenerarRequest, PreliquidacionResponse,
    LineaResponse, LineaUpdateRequest,
    ConceptoAdicionalRequest, ConceptoAdicionalResponse,
    ConceptoPorCodigoRequest,
    MensajeResponse,
)

router = APIRouter(prefix="/api/preliquidacion", tags=["Preliquidación"])


def get_service(
    db_propia: Session = Depends(get_db_propia),
    db_externa: Session = Depends(get_db_externa),
    db_sueldos: Session = Depends(get_db_sueldos),
) -> PreliquidacionService:
    return PreliquidacionService(db_propia, db_externa, db_sueldos)


@router.post("/generar", response_model=MensajeResponse)
def generar(
    req: PreliquidacionGenerarRequest,
    usuario=Depends(get_usuario_actual),
    service: PreliquidacionService = Depends(get_service),
):
    try:
        resultado = service.generar(quincena=req.quincena, usuario_id=usuario.id)
        stats = service.estadisticas(resultado["preliquidacion_id"])
        return MensajeResponse(
            mensaje="Preliquidación procesada correctamente",
            detalle=(
                f"{resultado['insertadas']} nuevas · "
                f"{resultado['eliminadas']} eliminadas · "
                f"{resultado['sin_cambios']} sin cambios — "
                f"Total: {stats['total_lineas']} líneas · "
                f"{stats['sin_precio']} sin precio · "
                f"{stats['duplicados']} duplicados"
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/empresas")
def listar_empresas(db_sueldos: Session = Depends(get_db_sueldos)):
    from sqlalchemy import text
    resultado = db_sueldos.execute(text(
        "SELECT DISTINCT empresa FROM nuempleados "
        "WHERE borrado IS NULL OR borrado <> 'S' "
        "ORDER BY empresa"
    )).fetchall()
    return [r[0].strip() for r in resultado if r[0]]


@router.get("/", response_model=list[PreliquidacionResponse])
def listar(service: PreliquidacionService = Depends(get_service)):
    preliquidaciones = service.listar()
    resultado = []
    for p in preliquidaciones:
        stats = service.estadisticas(p.id)
        resultado.append(PreliquidacionResponse(
            id=p.id, quincena=p.quincena, creado_en=p.creado_en,
            total_lineas=stats["total_lineas"],
            lineas_revisadas=stats["lineas_revisadas"],
            lineas_con_alerta=stats["lineas_con_alerta"],
        ))
    return resultado


# ─── Operación unificada ──────────────────────────────────────────────────────

@router.post("/{preliq_id}/aplicar", response_model=MensajeResponse)
def aplicar(
    preliq_id: int,
    service: PreliquidacionService = Depends(get_service),
):
    """Recalcula precios y aplica conceptos en una sola operación."""
    try:
        resultado = service.aplicar(preliq_id)
        return MensajeResponse(
            mensaje="Precios y conceptos aplicados",
            detalle=f"{resultado['actualizadas']} líneas con precio · {resultado['sin_precio']} sin precio · {resultado['conceptos_aplicados']} con conceptos"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Mantener endpoints viejos por compatibilidad ────────────────────────────

@router.post("/{preliq_id}/aplicar-conceptos", response_model=MensajeResponse)
def aplicar_conceptos(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        resultado = service.aplicar_conceptos(preliq_id)
        return MensajeResponse(mensaje="Conceptos aplicados", detalle=f"{resultado['actualizadas']} líneas actualizadas")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{preliq_id}/recalcular", response_model=MensajeResponse)
def recalcular_precios(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        resultado = service.recalcular_precios(preliq_id)
        return MensajeResponse(mensaje="Precios recalculados", detalle=f"{resultado['actualizadas']} líneas · {resultado['sin_precio']} sin precio")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{preliq_id}/backfill-conceptos", response_model=MensajeResponse)
def backfill_conceptos(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        resultado = service.backfill_detalles_conceptos(preliq_id)
        return MensajeResponse(mensaje="Detalles cargados", detalle=f"{resultado['insertados']} nuevos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/dashboard-verificacion")
def dashboard_verificacion(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    preliq = service.obtener(preliq_id)
    if not preliq:
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    try:
        return service.dashboard_verificacion(preliq_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/control-plantas-jornal")
def control_plantas_jornal(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    preliq = service.obtener(preliq_id)
    if not preliq:
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    try:
        return service.control_plantas_jornal(preliq_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/filtros")
def obtener_filtros(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    from sqlalchemy import text as sql_text
    db = service.db
    def unicos(campo):
        rows = db.execute(sql_text(
            f"SELECT DISTINCT {campo} FROM preliquidacion_linea "
            f"WHERE preliquidacion_id = :pid AND {campo} IS NOT NULL AND {campo} <> '' "
            f"ORDER BY {campo}"
        ), {"pid": preliq_id}).fetchall()
        return [r[0] for r in rows if r[0]]
    return {
        "clientes": unicos("nombre_cliente"), "fincas": unicos("nombre_finca"),
        "tareas": unicos("nombre_tarea"), "empresas": unicos("empresa_asignada"),
        "grupos_pago": unicos("grupo_pago_aplicado"), "supervisores": unicos("nombre_supervisor"),
    }


@router.get("/{preliq_id}/estadisticas")
def estadisticas(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    preliq = service.obtener(preliq_id)
    if not preliq:
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    return service.estadisticas(preliq_id)


@router.get("/{preliq_id}/lineas", response_model=list[LineaResponse])
def listar_lineas(
    preliq_id: int,
    empresa: Optional[str] = Query(None),
    revisado: Optional[bool] = Query(None),
    solo_alertas: Optional[bool] = Query(None),
    nombre_empleado: Optional[str] = Query(None),
    service: PreliquidacionService = Depends(get_service),
):
    preliq = service.obtener(preliq_id)
    if not preliq:
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    return service.listar_lineas(preliq_id=preliq_id, empresa=empresa, revisado=revisado,
                                  solo_alertas=solo_alertas, nombre_empleado=nombre_empleado)


@router.patch("/linea/{linea_id}", response_model=LineaResponse)
def actualizar_linea(linea_id: int, datos: LineaUpdateRequest, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    try:
        return service.actualizar_linea(linea_id=linea_id, datos=datos, usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/linea/{linea_id}/concepto", response_model=ConceptoAdicionalResponse)
def agregar_concepto(linea_id: int, datos: ConceptoAdicionalRequest, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    try:
        return service.agregar_concepto(linea_id=linea_id, datos=datos, usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/linea/{linea_id}/conceptos/por-codigo", response_model=ConceptoAdicionalResponse)
def agregar_concepto_por_codigo(
    linea_id: int,
    datos: ConceptoPorCodigoRequest,
    usuario=Depends(get_usuario_actual),
    service: PreliquidacionService = Depends(get_service),
):
    try:
        return service.agregar_concepto_por_codigo(linea_id, datos.codigo, usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/linea/concepto/{concepto_id}", response_model=MensajeResponse)
def eliminar_concepto(concepto_id: int, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    try:
        service.eliminar_concepto(concepto_id=concepto_id, usuario_id=usuario.id)
        return MensajeResponse(mensaje="Concepto eliminado correctamente")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class ConceptoMasivoRequest(BaseModel):
    linea_ids: list[int]
    codigo: int


@router.post("/lineas/concepto-masivo", response_model=MensajeResponse)
def agregar_concepto_masivo(datos: ConceptoMasivoRequest, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    if not datos.linea_ids or not datos.codigo:
        raise HTTPException(status_code=400, detail="Se requieren linea_ids y codigo")
    try:
        resultado = service.agregar_concepto_masivo(datos.linea_ids, datos.codigo, usuario.id)
        return MensajeResponse(mensaje="Concepto agregado", detalle=f"{resultado['aplicadas']} líneas actualizadas")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lineas/concepto-masivo/eliminar", response_model=MensajeResponse)
def eliminar_concepto_masivo(datos: ConceptoMasivoRequest, service: PreliquidacionService = Depends(get_service)):
    if not datos.linea_ids or not datos.codigo:
        raise HTTPException(status_code=400, detail="Se requieren linea_ids y codigo")
    try:
        resultado = service.eliminar_concepto_masivo(datos.linea_ids, datos.codigo)
        return MensajeResponse(mensaje="Concepto eliminado", detalle=f"{resultado['eliminados']} conceptos eliminados de {resultado['lineas']} líneas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))