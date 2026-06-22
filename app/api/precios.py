from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from app.core.database import get_db_propia, get_db_externa
from app.models.models import PrecioMaestro, PrecioComun
from app.services.consulta_externa import ConsultaExternaService
from app.schemas.schemas import (
    PrecioMaestroRequest, PrecioMaestroResponse,
    PrecioComunRequest, PrecioComunResponse,
    ConceptoLiquidacionRequest, ConceptoLiquidacionResponse,
    ConceptoLiquidacionUpdateRequest,
    MensajeResponse,
)
from app.models.models import ConceptoLiquidacion

router = APIRouter(prefix="/api/precios", tags=["Precios"])


@router.get("/maestro/clientes")
def listar_clientes(db_externa: Session = Depends(get_db_externa)):
    return ConsultaExternaService(db_externa).obtener_clientes()


@router.get("/maestro/fincas")
def listar_fincas(
    cliente: str = Query(...),
    db_externa: Session = Depends(get_db_externa),
):
    return ConsultaExternaService(db_externa).obtener_fincas(cliente)


@router.get("/maestro/tareas")
def listar_tareas(db_externa: Session = Depends(get_db_externa)):
    return ConsultaExternaService(db_externa).obtener_tareas()


@router.get("/maestro/faltantes/{preliq_id}")
def precios_faltantes(
    preliq_id: int,
    db_propia: Session = Depends(get_db_propia),
):
    """
    Devuelve las combinaciones cliente+finca+tarea que tienen lineas
    en la preliquidacion pero no tienen precio cargado en el maestro.
    El liquidador ve exactamente que falta antes de generar.
    """
    from sqlalchemy import text as sql_text

    # Traer quincena de la preliquidacion
    from app.models.models import Preliquidacion, PreliquidacionLinea
    preliq = db_propia.query(Preliquidacion).filter(
        Preliquidacion.id == preliq_id
    ).first()
    if not preliq:
        raise HTTPException(status_code=404, detail="Preliquidacion no encontrada")

    # Combinaciones unicas en las lineas de ESA preliquidacion solamente
    lineas = db_propia.execute(sql_text("""
        SELECT DISTINCT nombre_cliente, nombre_finca, nombre_tarea, grupo_pago_aplicado
        FROM preliquidacion_linea
        WHERE preliquidacion_id = :pid
          AND alerta_sin_precio = 1
        ORDER BY nombre_cliente, nombre_finca, nombre_tarea
    """), {"pid": preliq_id}).fetchall()
    
    if not lineas:
        return []

    # Para cada combinacion, buscar el ultimo precio conocido en quincenas anteriores
    faltantes = []
    for row in lineas:
        cliente, finca, tarea, grupo_pago = row
        ultimo = db_propia.query(PrecioMaestro).filter(
            and_(
                PrecioMaestro.cliente_nombre == cliente,
                PrecioMaestro.finca_nombre == finca,
                PrecioMaestro.tarea_nombre == tarea,
            )
        ).order_by(PrecioMaestro.quincena.desc()).first()

        faltantes.append({
            "cliente_nombre": cliente,
            "finca_nombre": finca,
            "tarea_nombre": tarea,
            "grupo_pago": grupo_pago,
            "quincena": str(preliq.quincena),
            "precio_sugerido": float(ultimo.precio_a) if ultimo and ultimo.precio_a else None,
            "quincena_sugerida": str(ultimo.quincena) if ultimo else None,
        })

    return faltantes


@router.get("/maestro/precio-sugerido")
def precio_sugerido(
    cliente: str = Query(...),
    finca: str = Query(...),
    tarea: str = Query(...),
    db: Session = Depends(get_db_propia),
):
    """
    Busca el precio mas reciente para cliente+finca+tarea en quincenas anteriores.
    Se usa como sugerencia cuando se agrega un precio nuevo que nunca existio.
    """
    ultimo = db.query(PrecioMaestro).filter(
        and_(
            PrecioMaestro.cliente_nombre == cliente,
            PrecioMaestro.finca_nombre == finca,
            PrecioMaestro.tarea_nombre == tarea,
        )
    ).order_by(PrecioMaestro.quincena.desc()).first()

    if not ultimo:
        return {"precio_a": None, "grupo_pago_default": None, "quincena": None}

    return {
        "precio_a": float(ultimo.precio_a) if ultimo.precio_a else None,
        "grupo_pago_default": ultimo.grupo_pago_default,
        "grupo_pago_override": ultimo.grupo_pago_override,
        "quincena": str(ultimo.quincena),
    }


@router.get("/maestro/quincenas")
def listar_quincenas_con_precios(db: Session = Depends(get_db_propia)):
    """Lista de quincenas que ya tienen precios MAESTRO (específicos) cargados, ordenadas desc."""
    from sqlalchemy import distinct
    resultado = db.query(distinct(PrecioMaestro.quincena)).order_by(
        PrecioMaestro.quincena.desc()
    ).all()
    return [str(r[0]) for r in resultado]


@router.get("/maestro", response_model=list[PrecioMaestroResponse])
def listar_precios_maestro(
    quincena: Optional[date] = Query(None),
    cliente: Optional[str] = Query(None),
    db: Session = Depends(get_db_propia),
):
    q = db.query(PrecioMaestro)
    if quincena:
        q = q.filter(PrecioMaestro.quincena == quincena)
    if cliente:
        q = q.filter(PrecioMaestro.cliente_nombre == cliente)
    return q.order_by(
        PrecioMaestro.cliente_nombre,
        PrecioMaestro.finca_nombre,
        PrecioMaestro.tarea_nombre,
    ).all()


@router.post("/maestro", response_model=PrecioMaestroResponse)
def crear_precio_maestro(datos: PrecioMaestroRequest, db: Session = Depends(get_db_propia)):
    existente = db.query(PrecioMaestro).filter(
        and_(
            PrecioMaestro.cliente_nombre == datos.cliente_nombre,
            PrecioMaestro.finca_nombre == datos.finca_nombre,
            PrecioMaestro.tarea_nombre == datos.tarea_nombre,
            PrecioMaestro.quincena == datos.quincena,
        )
    ).first()

    if existente:
        existente.grupo_pago_default = datos.grupo_pago_default
        existente.grupo_pago_override = datos.grupo_pago_override
        existente.precio_a = datos.precio_a
        db.commit()
        db.refresh(existente)
        return existente

    precio = PrecioMaestro(**datos.model_dump())
    db.add(precio)
    db.commit()
    db.refresh(precio)
    return precio


@router.post("/maestro/copiar-quincena", response_model=MensajeResponse)
def copiar_quincena(
    quincena_origen: date = Query(..., description="Quincena a copiar"),
    quincena_destino: date = Query(..., description="Nueva quincena"),
    db: Session = Depends(get_db_propia),
):
    """
    Copia todos los precios ESPECÍFICOS (precio_maestro) de una quincena a otra.
    Si ya existen precios en destino para una combinacion, los omite.
    """
    precios_origen = db.query(PrecioMaestro).filter(
        PrecioMaestro.quincena == quincena_origen
    ).all()

    if not precios_origen:
        raise HTTPException(status_code=404, detail=f"No hay precios específicos para la quincena {quincena_origen}")

    copiados = 0
    omitidos = 0
    for p in precios_origen:
        existente = db.query(PrecioMaestro).filter(
            and_(
                PrecioMaestro.cliente_nombre == p.cliente_nombre,
                PrecioMaestro.finca_nombre == p.finca_nombre,
                PrecioMaestro.tarea_nombre == p.tarea_nombre,
                PrecioMaestro.quincena == quincena_destino,
            )
        ).first()
        if existente:
            omitidos += 1
            continue
        nuevo = PrecioMaestro(
            cliente_nombre=p.cliente_nombre,
            finca_nombre=p.finca_nombre,
            tarea_nombre=p.tarea_nombre,
            grupo_pago_default=p.grupo_pago_default,
            grupo_pago_override=p.grupo_pago_override,
            quincena=quincena_destino,
            precio_a=p.precio_a,
        )
        db.add(nuevo)
        copiados += 1

    db.commit()
    return MensajeResponse(
        mensaje=f"Precios específicos copiados correctamente",
        detalle=f"{copiados} precios copiados · {omitidos} ya existían en destino"
    )


@router.patch("/maestro/{precio_id}", response_model=PrecioMaestroResponse)
def actualizar_precio_maestro(
    precio_id: int,
    datos: PrecioMaestroRequest,
    db: Session = Depends(get_db_propia),
):
    """Actualiza un precio existente del maestro (para edición inline)."""
    precio = db.query(PrecioMaestro).filter(PrecioMaestro.id == precio_id).first()
    if not precio:
        raise HTTPException(status_code=404, detail="Precio no encontrado")
    precio.grupo_pago_default = datos.grupo_pago_default
    precio.grupo_pago_override = datos.grupo_pago_override
    precio.precio_a = datos.precio_a
    db.commit()
    db.refresh(precio)
    return precio


@router.delete("/maestro/{precio_id}", response_model=MensajeResponse)
def eliminar_precio_maestro(precio_id: int, db: Session = Depends(get_db_propia)):
    precio = db.query(PrecioMaestro).filter(PrecioMaestro.id == precio_id).first()
    if not precio:
        raise HTTPException(status_code=404, detail="Precio no encontrado")
    db.delete(precio)
    db.commit()
    return MensajeResponse(mensaje="Precio eliminado")


@router.get("/comunes/quincenas")
def listar_quincenas_con_precios_comunes(db: Session = Depends(get_db_propia)):
    """Lista de quincenas que ya tienen precios COMUNES cargados, ordenadas desc."""
    from sqlalchemy import distinct
    resultado = db.query(distinct(PrecioComun.quincena)).order_by(
        PrecioComun.quincena.desc()
    ).all()
    return [str(r[0]) for r in resultado]


@router.get("/comunes", response_model=list[PrecioComunResponse])
def listar_precios_comunes(
    quincena: Optional[date] = Query(None),
    db: Session = Depends(get_db_propia),
):
    q = db.query(PrecioComun)
    if quincena:
        q = q.filter(PrecioComun.quincena == quincena)
    return q.order_by(PrecioComun.tarea_nombre).all()


@router.post("/comunes", response_model=PrecioComunResponse)
def crear_precio_comun(datos: PrecioComunRequest, db: Session = Depends(get_db_propia)):
    existente = db.query(PrecioComun).filter(
        and_(
            PrecioComun.tarea_nombre == datos.tarea_nombre,
            PrecioComun.grupo_pago == datos.grupo_pago,
            PrecioComun.quincena == datos.quincena,
        )
    ).first()

    if existente:
        existente.precio = datos.precio
        db.commit()
        db.refresh(existente)
        return existente

    precio = PrecioComun(**datos.model_dump())
    db.add(precio)
    db.commit()
    db.refresh(precio)
    return precio


@router.post("/comunes/copiar-quincena", response_model=MensajeResponse)
def copiar_quincena_comunes(
    quincena_origen: date = Query(..., description="Quincena a copiar"),
    quincena_destino: date = Query(..., description="Nueva quincena"),
    db: Session = Depends(get_db_propia),
):
    """
    Copia todos los precios COMUNES (precio_comun) de una quincena a otra.
    Si ya existen precios en destino para una combinacion tarea+grupo_pago,
    los omite (no pisa lo que el liquidador ya cargó).
    """
    precios_origen = db.query(PrecioComun).filter(
        PrecioComun.quincena == quincena_origen
    ).all()

    if not precios_origen:
        raise HTTPException(status_code=404, detail=f"No hay precios comunes para la quincena {quincena_origen}")

    copiados = 0
    omitidos = 0
    for p in precios_origen:
        existente = db.query(PrecioComun).filter(
            and_(
                PrecioComun.tarea_nombre == p.tarea_nombre,
                PrecioComun.grupo_pago == p.grupo_pago,
                PrecioComun.quincena == quincena_destino,
            )
        ).first()
        if existente:
            omitidos += 1
            continue
        nuevo = PrecioComun(
            tarea_nombre=p.tarea_nombre,
            grupo_pago=p.grupo_pago,
            quincena=quincena_destino,
            precio=p.precio,
        )
        db.add(nuevo)
        copiados += 1

    db.commit()
    return MensajeResponse(
        mensaje=f"Precios comunes copiados correctamente",
        detalle=f"{copiados} precios copiados · {omitidos} ya existían en destino"
    )


@router.delete("/comunes/{precio_id}", response_model=MensajeResponse)
def eliminar_precio_comun(precio_id: int, db: Session = Depends(get_db_propia)):
    precio = db.query(PrecioComun).filter(PrecioComun.id == precio_id).first()
    if not precio:
        raise HTTPException(status_code=404, detail="Precio no encontrado")
    db.delete(precio)
    db.commit()
    return MensajeResponse(mensaje="Precio eliminado")


@router.get("/grupos-pago")
def listar_grupos_pago(db_externa: Session = Depends(get_db_externa)):
    """Lista de grupos de pago únicos disponibles en el sistema."""
    resultado = db_externa.execute(text("""
        SELECT DISTINCT
            TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 2), ';', -1)) AS grupo_pago
        FROM laa_tareas ta
        WHERE ta.estado <> 9
          AND ta.descripcion IS NOT NULL
          AND ta.descripcion <> ''
        ORDER BY grupo_pago
    """))
    grupos = [fila[0] for fila in resultado.fetchall() if fila[0]]
    return grupos


# ─── Maestro de Conceptos de Liquidación ──────────────────────────────────────
# Un mismo `detalle` puede tener varias reglas (códigos). El liquidador
# las define una vez y se aplican de forma pasiva a todas las líneas
# que matcheen ese detalle.

@router.get("/conceptos", response_model=list[ConceptoLiquidacionResponse])
def listar_conceptos(
    detalle: str | None = None,
    db_propia: Session = Depends(get_db_propia),
):
    q = db_propia.query(ConceptoLiquidacion)
    if detalle:
        q = q.filter(ConceptoLiquidacion.detalle.ilike(f"%{detalle}%"))
    return q.order_by(ConceptoLiquidacion.detalle, ConceptoLiquidacion.codigo).all()


@router.get("/conceptos/agrupados")
def listar_conceptos_agrupados(
    busqueda: str | None = None,
    solo_sin_reglas: bool = False,
    db_propia: Session = Depends(get_db_propia),
):
    """
    Agrupa las reglas de concepto_liquidacion por `detalle`.
    Devuelve: [{ detalle, reglas: [...] }]
    """
    q = db_propia.query(ConceptoLiquidacion)
    if busqueda:
        q = q.filter(ConceptoLiquidacion.detalle.ilike(f"%{busqueda}%"))

    todos = q.order_by(ConceptoLiquidacion.detalle, ConceptoLiquidacion.codigo).all()

    agrupados = {}
    for c in todos:
        agrupados.setdefault(c.detalle, []).append(c)

    resultado = []
    for detalle, reglas in agrupados.items():
        tiene_reglas_con_codigo = any(r.codigo is not None for r in reglas)
        if solo_sin_reglas and tiene_reglas_con_codigo:
            continue
        resultado.append({
            "detalle": detalle,
            "reglas": [
                {
                    "id": r.id,
                    "codigo": r.codigo,
                    "unidad_base": r.unidad_base.value if hasattr(r.unidad_base, "value") else r.unidad_base,
                    "precio": float(r.precio) if r.precio is not None else None,
                    "tipo": r.tipo.value if hasattr(r.tipo, "value") else r.tipo,
                }
                for r in reglas
            ],
        })

    return resultado


@router.get("/conceptos/detalles")
def listar_detalles_unicos(db_propia: Session = Depends(get_db_propia)):
    """Lista los `detalle` únicos — para que el liquidador elija sobre cuál agregar reglas."""
    rows = db_propia.query(ConceptoLiquidacion.detalle).distinct().order_by(ConceptoLiquidacion.detalle).all()
    return [r[0] for r in rows]


@router.post("/conceptos", response_model=ConceptoLiquidacionResponse)
def crear_concepto(
    datos: ConceptoLiquidacionRequest,
    db_propia: Session = Depends(get_db_propia),
):
    """Agrega una regla (código + UM + precio) a un detalle. Un detalle puede tener varias."""
    nuevo = ConceptoLiquidacion(
        detalle=datos.detalle.strip().upper(),
        codigo=datos.codigo,
        unidad_base=datos.unidad_base,
        precio=datos.precio,
        tipo=datos.tipo,
    )
    db_propia.add(nuevo)
    try:
        db_propia.commit()
    except Exception as e:
        db_propia.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo guardar: {e}")
    db_propia.refresh(nuevo)
    return nuevo


@router.patch("/conceptos/{concepto_id}", response_model=ConceptoLiquidacionResponse)
def actualizar_concepto(
    concepto_id: int,
    datos: ConceptoLiquidacionUpdateRequest,
    db_propia: Session = Depends(get_db_propia),
):
    concepto = db_propia.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.id == concepto_id
    ).first()
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(concepto, campo, valor)

    db_propia.commit()
    db_propia.refresh(concepto)
    return concepto


@router.delete("/conceptos/{concepto_id}", response_model=MensajeResponse)
def eliminar_concepto(
    concepto_id: int,
    db_propia: Session = Depends(get_db_propia),
):
    concepto = db_propia.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.id == concepto_id
    ).first()
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    db_propia.delete(concepto)
    db_propia.commit()
    return MensajeResponse(mensaje="Concepto eliminado")


@router.get("/conceptos/buscar")
def buscar_conceptos_para_combo(
    q: str = "",
    db_propia: Session = Depends(get_db_propia),
):
    """
    Búsqueda con coincidencia parcial por código, para el combo de
    autocompletado del panel de línea. Devuelve códigos únicos con su tipo
    (si un código se repite en varios detalles, se toma el primero).
    """
    query = db_propia.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.codigo.isnot(None)
    )
    if q:
        if q.strip().isdigit():
            query = query.filter(ConceptoLiquidacion.codigo == int(q.strip()))
        else:
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