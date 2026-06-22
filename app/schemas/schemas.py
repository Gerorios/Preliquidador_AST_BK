from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from app.models.models import TipoConcepto, PrecioUsado


class PreliquidacionGenerarRequest(BaseModel):
    quincena: date


class PreliquidacionResponse(BaseModel):
    id: int
    quincena: date
    creado_en: datetime
    total_lineas: int
    lineas_revisadas: int
    lineas_con_alerta: int

    class Config:
        from_attributes = True

class ConceptoAdicionalResponse(BaseModel):
    id: int
    descripcion: str
    tipo: Optional[TipoConcepto]
    importe: Decimal
    codigo_concepto: Optional[int] = None   # ← agregar
    ingresado_por: Optional[int] = None     # ← agregar

    class Config:
        from_attributes = True


class LineaResponse(BaseModel):
    id: int
    preliquidacion_id: int
    planilla: Optional[str]
    fecha_tarea: Optional[date]
    nombre_cliente: Optional[str]
    nombre_finca: Optional[str]
    nombre_tarea: Optional[str]
    nombre_tractor: Optional[str]
    legajo_campo: Optional[str]
    nombre_empleado: Optional[str]
    cuit: Optional[str]
    nombre_supervisor: Optional[str]
    nombre_capataz: Optional[str]
    implemento: Optional[str]
    unidades: Optional[Decimal]
    tancadas: Optional[Decimal]
    hsjornal: Optional[Decimal]
    hsmaquina: Optional[Decimal]
    cantidad: Optional[Decimal]
    empresa_asignada: Optional[str]
    legajo_asignado: Optional[str]
    grupo_pago_aplicado: Optional[str]
    precio_a: Optional[Decimal]
    precio_b: Optional[Decimal]
    precio_usado: Optional[PrecioUsado]
    importe_base: Optional[Decimal]
    importe_total: Optional[Decimal]
    revisado: bool
    observacion: Optional[str]
    es_duplicado: bool
    alerta_legajo: bool
    alerta_empresa: bool = False
    alerta_sin_precio: bool
    conceptos: list[ConceptoAdicionalResponse] = []

    class Config:
        from_attributes = True


class LineaUpdateRequest(BaseModel):
    empresa_asignada: Optional[str] = None
    legajo_asignado: Optional[str] = None
    grupo_pago_aplicado: Optional[str] = None
    precio_b: Optional[Decimal] = None
    precio_usado: Optional[PrecioUsado] = None
    revisado: Optional[bool] = None
    observacion: Optional[str] = None
    motivo_ajuste: Optional[str] = None


class ConceptoAdicionalRequest(BaseModel):
    descripcion: str
    tipo: TipoConcepto = TipoConcepto.OTRO
    importe: Decimal


class PrecioMaestroRequest(BaseModel):
    cliente_nombre: str
    finca_nombre: str
    tarea_nombre: str
    grupo_pago_default: str
    grupo_pago_override: Optional[str] = None
    quincena: date
    precio_a: Optional[Decimal] = None


class PrecioMaestroResponse(BaseModel):
    id: int
    cliente_nombre: str
    finca_nombre: str
    tarea_nombre: str
    grupo_pago_default: str
    grupo_pago_override: Optional[str]
    quincena: date
    precio_a: Optional[Decimal]
    actualizado_en: datetime

    class Config:
        from_attributes = True


class PrecioComunRequest(BaseModel):
    tarea_nombre: str
    grupo_pago: str
    quincena: date
    precio: Decimal


class PrecioComunResponse(BaseModel):
    id: int
    tarea_nombre: str
    grupo_pago: str
    quincena: date
    precio: Decimal
    actualizado_en: datetime

    class Config:
        from_attributes = True


class MensajeResponse(BaseModel):
    mensaje: str
    detalle: Optional[str] = None


# ─── Maestro de Conceptos de Liquidación ──────────────────────────────────────
# Cada `detalle` puede tener varias reglas (códigos) asociadas.

from app.models.models import UnidadBaseConcepto


class ConceptoLiquidacionResponse(BaseModel):
    id: int
    detalle: str
    codigo: Optional[int] = None
    unidad_base: UnidadBaseConcepto
    precio: Optional[Decimal] = None
    tipo: TipoConcepto

    class Config:
        from_attributes = True


class ConceptoLiquidacionRequest(BaseModel):
    detalle: str
    codigo: Optional[int] = None
    unidad_base: UnidadBaseConcepto = UnidadBaseConcepto.FIJO
    precio: Optional[Decimal] = None
    tipo: TipoConcepto = TipoConcepto.OTRO


class ConceptoLiquidacionUpdateRequest(BaseModel):
    codigo: Optional[int] = None
    unidad_base: Optional[UnidadBaseConcepto] = None
    precio: Optional[Decimal] = None
    tipo: Optional[TipoConcepto] = None


class ConceptoPorCodigoRequest(BaseModel):
    codigo: int
