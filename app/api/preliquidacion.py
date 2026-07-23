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
    MensajeResponse, ValorHoraPulvRequest,
    CategoriaOperarioRequest, OperarioMantenimientoResponse,
)

# dependencies: TODOS los endpoints del router exigen sesión válida — antes
# los GET (líneas, dashboard, estadísticas, etc.) eran públicos y exponían
# datos de liquidación sin token. El costo por request es ~0: get_usuario_actual
# cachea el usuario 60s y FastAPI deduplica la dependencia si el endpoint
# también la declara como parámetro.
router = APIRouter(
    prefix="/api/preliquidacion",
    tags=["Preliquidación"],
    dependencies=[Depends(get_usuario_actual)],
)


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
                f"{stats['incompletas']} incompletas · "
                f"{stats['duplicados']} duplicados"
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refrescar-sueldos", response_model=MensajeResponse)
def refrescar_sueldos(_=Depends(get_usuario_actual)):
    """Marca el maestro de sueldos (cache de proceso) para recargarse en el
    próximo uso. Útil cuando cambió nuempleados y no se quiere esperar al TTL."""
    from app.services.sueldos_service import refrescar_cache_sueldos
    refrescar_cache_sueldos()
    invalidar_cache_empresas()
    return MensajeResponse(mensaje="Maestro de sueldos marcado para refrescar")


# Cache de proceso de la lista de empresas: es un DISTINCT sobre nuempleados
# (15-19k filas) en la base remota de sueldos (~1.5s por llamada) y el listado
# cambia casi nunca. TTL 10 min; "refrescar sueldos" también lo limpia.
_EMPRESAS_CACHE: dict = {"datos": None, "expira": 0.0}
_EMPRESAS_CACHE_TTL = 600  # segundos


def invalidar_cache_empresas():
    _EMPRESAS_CACHE["datos"] = None
    _EMPRESAS_CACHE["expira"] = 0.0


@router.get("/empresas")
def listar_empresas(db_sueldos: Session = Depends(get_db_sueldos)):
    import time
    from sqlalchemy import text
    if _EMPRESAS_CACHE["datos"] is not None and _EMPRESAS_CACHE["expira"] > time.monotonic():
        return _EMPRESAS_CACHE["datos"]
    resultado = db_sueldos.execute(text(
        "SELECT DISTINCT empresa FROM nuempleados "
        "WHERE borrado IS NULL OR borrado <> 'S' "
        "ORDER BY empresa"
    )).fetchall()
    empresas = [r[0].strip() for r in resultado if r[0]]
    _EMPRESAS_CACHE["datos"] = empresas
    _EMPRESAS_CACHE["expira"] = time.monotonic() + _EMPRESAS_CACHE_TTL
    return empresas


@router.get("/", response_model=list[PreliquidacionResponse])
def listar(service: PreliquidacionService = Depends(get_service)):
    preliquidaciones = service.listar()
    stats_por_id = service.estadisticas_batch([p.id for p in preliquidaciones])
    resultado = []
    for p in preliquidaciones:
        stats = stats_por_id[p.id]
        resultado.append(PreliquidacionResponse(
            id=p.id, quincena=p.quincena, creado_en=p.creado_en,
            total_lineas=stats["total_lineas"],
            lineas_con_alerta=stats["lineas_con_alerta"],
        ))
    return resultado


@router.post("/{preliq_id}/backfill-conceptos", response_model=MensajeResponse)
def backfill_conceptos(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        resultado = service.backfill_detalles_conceptos(preliq_id)
        return MensajeResponse(mensaje="Detalles cargados", detalle=f"{resultado['insertados']} nuevos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Estos endpoints ya no hacen el obtener() previo: el servicio detecta la
# preliquidación inexistente (ValueError → 404). Con la base remota, ese
# precheck costaba un round-trip entero (~200ms) en cada carga de pantalla.

@router.get("/{preliq_id}/dashboard-verificacion")
def dashboard_verificacion(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        return service.dashboard_verificacion(preliq_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/control-plantas-jornal")
def control_plantas_jornal(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        return service.control_plantas_jornal(preliq_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/control-tancadas-jornal")
def control_tancadas_jornal(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    try:
        return service.control_tancadas_jornal(preliq_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preliq_id}/operarios-mantenimiento", response_model=list[OperarioMantenimientoResponse])
def operarios_mantenimiento(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    """Operarios (por CUIL) con líneas de taller (Mantenimiento mecánico) en
    esta quincena, junto con la categoría ya asignada (ADR-0008)."""
    try:
        return service.operarios_mantenimiento(preliq_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{preliq_id}/categoria-operario")
def set_categoria_operario(
    preliq_id: int,
    datos: CategoriaOperarioRequest,
    service: PreliquidacionService = Depends(get_service),
):
    """Asigna (o borra, con categoria=null) la categoría de una persona para
    la quincena de esta preliquidación y recalcula sus líneas de taller."""
    try:
        return service.set_categoria_operario(preliq_id, datos.cuil, datos.categoria)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{preliq_id}/categorias-operario/heredar", response_model=MensajeResponse)
def heredar_categorias_operario(preliq_id: int, service: PreliquidacionService = Depends(get_service)):
    """Copia las asignaciones de categoría de la quincena anterior hacia
    esta, para los CUIL que todavía no tengan asignación."""
    try:
        resultado = service.heredar_categorias_operario(preliq_id)
        return MensajeResponse(mensaje="Categorías heredadas", detalle=f"{resultado['heredados']} operarios")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{preliq_id}/valor-hora-pulv")
def set_valor_hora_pulv(preliq_id: int, datos: ValorHoraPulvRequest, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    try:
        preliq = service.set_valor_hora_pulv(preliq_id, datos.valor_hora_pulv)
        return {"valor_hora_pulv": float(preliq.valor_hora_pulv) if preliq.valor_hora_pulv is not None else None}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    stats = service.estadisticas(preliq_id)
    # Solo si la quincena vino vacía vale la pena pagar el round-trip extra
    # para distinguir "preliquidación sin líneas" de "no existe" (404).
    if stats["total_lineas"] == 0 and not service.obtener(preliq_id):
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    return stats


@router.get("/{preliq_id}/lineas", response_model=list[LineaResponse])
def listar_lineas(
    preliq_id: int,
    empresa: Optional[str] = Query(None),
    solo_alertas: Optional[bool] = Query(None),
    nombre_empleado: Optional[str] = Query(None),
    service: PreliquidacionService = Depends(get_service),
):
    lineas = service.listar_lineas(preliq_id=preliq_id, empresa=empresa,
                                   solo_alertas=solo_alertas, nombre_empleado=nombre_empleado)
    # Round-trip de existencia solo en el caso raro de respuesta vacía, para
    # mantener el 404 de siempre cuando el id no existe.
    if not lineas and not service.obtener(preliq_id):
        raise HTTPException(status_code=404, detail="Preliquidación no encontrada")
    return lineas


@router.patch("/linea/{linea_id}", response_model=LineaResponse)
def actualizar_linea(linea_id: int, datos: LineaUpdateRequest, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    try:
        return service.actualizar_linea(linea_id=linea_id, datos=datos, usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/linea/{linea_id}/legajos-disponibles")
def legajos_disponibles_de_linea(linea_id: int, usuario=Depends(get_usuario_actual), service: PreliquidacionService = Depends(get_service)):
    """
    Pares (empresa, legajo) reales de la persona de esta línea, para el
    desplegable 'EMPRESA — legajo' del panel individual. Lista vacía si la
    línea no tiene CUIL (el front cae al campo manual en ese caso).
    """
    try:
        return service.legajos_disponibles_de_linea(linea_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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


# ─── Reasignación masiva de empresa ────────────────────────────────────────────

class LegajosPorCuilRequest(BaseModel):
    linea_ids: list[int]


class ReasignarEmpresaRequest(BaseModel):
    linea_ids: list[int]
    empresa: str
    motivo_ajuste: Optional[str] = None


@router.post("/lineas/legajos-por-cuil")
def legajos_por_cuil(datos: LegajosPorCuilRequest, service: PreliquidacionService = Depends(get_service)):
    """
    Agrupa las líneas seleccionadas por CUIL y devuelve, para cada persona,
    los pares (empresa, legajo) que realmente tiene — para el picker de
    reasignación masiva de empresa.
    """
    if not datos.linea_ids:
        raise HTTPException(status_code=400, detail="Se requieren linea_ids")
    try:
        return service.legajos_disponibles_por_cuil(datos.linea_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lineas/reasignar-empresa", response_model=MensajeResponse)
def reasignar_empresa_masivo(
    datos: ReasignarEmpresaRequest,
    usuario=Depends(get_usuario_actual),
    service: PreliquidacionService = Depends(get_service),
):
    if not datos.linea_ids or not datos.empresa:
        raise HTTPException(status_code=400, detail="Se requieren linea_ids y empresa")
    try:
        resultado = service.reasignar_empresa_masivo(
            datos.linea_ids, datos.empresa, usuario.id, motivo=datos.motivo_ajuste
        )
        detalle = f"{resultado['reasignadas']} líneas reasignadas a {datos.empresa}"
        if resultado["sin_legajo_en_empresa"]:
            detalle += f" · {len(resultado['sin_legajo_en_empresa'])} sin legajo en esa empresa (no se tocaron)"
        return MensajeResponse(mensaje="Empresa reasignada", detalle=detalle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))