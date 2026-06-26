from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from app.core.database import get_db_propia, get_db_externa
from app.models.models import ConceptoLiquidacion
from app.services.consulta_externa import ConsultaExternaService
from app.schemas.schemas import (
    ConceptoUnifRequest, ConceptoUnifResponse, ConceptoUnifUpdateRequest,
    MensajeResponse,
)

router = APIRouter(prefix="/api/precios", tags=["Precios"])


# ─── Catálogos externos ───────────────────────────────────────────────────────

@router.get("/maestro/clientes")
def listar_clientes(db_externa: Session = Depends(get_db_externa)):
    return ConsultaExternaService(db_externa).obtener_clientes()


@router.get("/maestro/fincas")
def listar_fincas(cliente: str = Query(...), db_externa: Session = Depends(get_db_externa)):
    return ConsultaExternaService(db_externa).obtener_fincas(cliente)


@router.get("/maestro/tareas")
def listar_tareas(db_externa: Session = Depends(get_db_externa)):
    return ConsultaExternaService(db_externa).obtener_tareas()


@router.get("/grupos-pago")
def listar_grupos_pago(db_externa: Session = Depends(get_db_externa)):
    resultado = db_externa.execute(text("""
        SELECT DISTINCT
            TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 2), ';', -1)) AS grupo_pago
        FROM laa_tareas ta
        WHERE ta.estado <> 9
          AND ta.descripcion IS NOT NULL
          AND ta.descripcion <> ''
        ORDER BY grupo_pago
    """))
    return [fila[0] for fila in resultado.fetchall() if fila[0]]


# ─── Maestro unificado de Conceptos de Liquidación ───────────────────────────
#
# cliente_nombre IS NULL  → concepto COMÚN  (aplica a todas las líneas con esa tarea)
# cliente_nombre NOT NULL → concepto ESPECÍFICO (solo cliente+finca exactos)
# Ambos tipos siempre suman.

@router.get("/conceptos/quincenas")
def listar_quincenas(db: Session = Depends(get_db_propia)):
    from sqlalchemy import distinct
    rows = db.query(distinct(ConceptoLiquidacion.quincena)).order_by(
        ConceptoLiquidacion.quincena.desc()
    ).all()
    return [str(r[0]) for r in rows]


@router.get("/conceptos", response_model=list[ConceptoUnifResponse])
def listar_conceptos(
    quincena: Optional[date] = Query(None),
    scope: Optional[str] = Query(None),   # 'comun' | 'especifico'
    tarea: Optional[str] = Query(None),
    db: Session = Depends(get_db_propia),
):
    q = db.query(ConceptoLiquidacion)
    if quincena:
        q = q.filter(ConceptoLiquidacion.quincena == quincena)
    if scope == "comun":
        q = q.filter(ConceptoLiquidacion.cliente_nombre.is_(None))
    elif scope == "especifico":
        q = q.filter(ConceptoLiquidacion.cliente_nombre.isnot(None))
    if tarea:
        q = q.filter(ConceptoLiquidacion.tarea_nombre.ilike(f"%{tarea}%"))
    return q.order_by(
        ConceptoLiquidacion.tarea_nombre,
        ConceptoLiquidacion.cliente_nombre,
        ConceptoLiquidacion.finca_nombre,
        ConceptoLiquidacion.codigo,
    ).all()


@router.post("/conceptos", response_model=ConceptoUnifResponse)
def crear_concepto(datos: ConceptoUnifRequest, db: Session = Depends(get_db_propia)):
    nuevo = ConceptoLiquidacion(
        quincena=datos.quincena,
        tarea_nombre=datos.tarea_nombre.strip(),
        cliente_nombre=datos.cliente_nombre.strip() if datos.cliente_nombre else None,
        finca_nombre=datos.finca_nombre.strip() if datos.finca_nombre else None,
        codigo=datos.codigo,
        unidad_base=datos.unidad_base,
        precio=datos.precio,
        tipo=datos.tipo,
    )
    db.add(nuevo)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo guardar: {e}")
    db.refresh(nuevo)
    return nuevo


@router.patch("/conceptos/{concepto_id}", response_model=ConceptoUnifResponse)
def actualizar_concepto(
    concepto_id: int,
    datos: ConceptoUnifUpdateRequest,
    db: Session = Depends(get_db_propia),
):
    concepto = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.id == concepto_id
    ).first()
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(concepto, campo, valor)
    db.commit()
    db.refresh(concepto)
    return concepto


@router.delete("/conceptos/{concepto_id}", response_model=MensajeResponse)
def eliminar_concepto(concepto_id: int, db: Session = Depends(get_db_propia)):
    concepto = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.id == concepto_id
    ).first()
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    db.delete(concepto)
    db.commit()
    return MensajeResponse(mensaje="Concepto eliminado")


@router.post("/conceptos/copiar", response_model=MensajeResponse)
def copiar_quincena(
    quincena_origen: date = Query(...),
    quincena_destino: date = Query(...),
    db: Session = Depends(get_db_propia),
):
    """Copia todos los conceptos de una quincena a otra. Omite los que ya existen."""
    origen = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena_origen
    ).all()
    if not origen:
        raise HTTPException(status_code=404, detail=f"No hay conceptos para {quincena_origen}")

    copiados = omitidos = 0
    for c in origen:
        existe = db.query(ConceptoLiquidacion).filter(
            and_(
                ConceptoLiquidacion.quincena       == quincena_destino,
                ConceptoLiquidacion.tarea_nombre   == c.tarea_nombre,
                ConceptoLiquidacion.cliente_nombre == c.cliente_nombre,
                ConceptoLiquidacion.finca_nombre   == c.finca_nombre,
                ConceptoLiquidacion.codigo         == c.codigo,
            )
        ).first()
        if existe:
            omitidos += 1
            continue
        db.add(ConceptoLiquidacion(
            quincena=quincena_destino,
            tarea_nombre=c.tarea_nombre,
            cliente_nombre=c.cliente_nombre,
            finca_nombre=c.finca_nombre,
            codigo=c.codigo,
            unidad_base=c.unidad_base,
            precio=c.precio,
            tipo=c.tipo,
        ))
        copiados += 1

    db.commit()
    return MensajeResponse(
        mensaje="Conceptos copiados",
        detalle=f"{copiados} copiados · {omitidos} ya existían",
    )


@router.get("/conceptos/faltantes")
def conceptos_faltantes(
    quincena: date = Query(...),
    db: Session = Depends(get_db_propia),
):
    """
    Combinaciones tarea+cliente+finca de la quincena que no tienen
    ningún concepto cargado (ni común ni específico).
    """
    rows = db.execute(text("""
        SELECT DISTINCT
            pl.nombre_tarea,
            pl.nombre_cliente,
            pl.nombre_finca
        FROM preliquidacion_linea pl
        INNER JOIN preliquidacion p ON p.id = pl.preliquidacion_id
        WHERE p.quincena = :quincena
          AND NOT EXISTS (
              SELECT 1 FROM concepto_liquidacion cl
              WHERE cl.quincena = :quincena
                AND cl.tarea_nombre = pl.nombre_tarea
                AND (
                    cl.cliente_nombre IS NULL
                    OR (cl.cliente_nombre = pl.nombre_cliente
                        AND cl.finca_nombre = pl.nombre_finca)
                )
          )
        ORDER BY pl.nombre_tarea, pl.nombre_cliente, pl.nombre_finca
    """), {"quincena": quincena}).fetchall()

    return [
        {"tarea_nombre": r[0], "cliente_nombre": r[1], "finca_nombre": r[2]}
        for r in rows
    ]


@router.get("/conceptos/buscar")
def buscar_conceptos_para_combo(
    q: str = "",
    quincena: Optional[date] = Query(None),
    db: Session = Depends(get_db_propia),
):
    """Búsqueda de códigos para el combo del PanelLinea."""
    query = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.codigo.isnot(None)
    )
    if quincena:
        query = query.filter(ConceptoLiquidacion.quincena == quincena)
    if q and q.strip().isdigit():
        query = query.filter(ConceptoLiquidacion.codigo == int(q.strip()))
    elif q:
        query = query.filter(ConceptoLiquidacion.tipo.ilike(f"%{q}%"))

    filas = query.order_by(ConceptoLiquidacion.codigo).limit(200).all()
    vistos = set()
    resultado = []
    for c in filas:
        if c.codigo in vistos:
            continue
        vistos.add(c.codigo)
        resultado.append({
            "codigo": c.codigo,
            "tipo": c.tipo.value if hasattr(c.tipo, "value") else c.tipo,
        })
    return resultado