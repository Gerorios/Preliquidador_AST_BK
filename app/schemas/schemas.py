from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from app.models.models import TipoConcepto, UnidadBaseConcepto


class PreliquidacionGenerarRequest(BaseModel):
    quincena: date


class PreliquidacionResponse(BaseModel):
    id: int
    quincena: date
    creado_en: datetime
    total_lineas: int
    lineas_con_alerta: int

    class Config:
        from_attributes = True


class ConceptoAdicionalResponse(BaseModel):
    id: int
    descripcion: str
    tipo: Optional[TipoConcepto]
    importe: Decimal
    codigo_concepto: Optional[int] = None
    unidad_base: Optional[str] = None
    precio: Optional[Decimal] = None
    cantidad: Optional[Decimal] = None
    concepto_liquidacion_id: Optional[int] = None
    ingresado_por: Optional[int] = None

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
    importe_base: Optional[Decimal]
    importe_total: Optional[Decimal]
    observacion: Optional[str]
    es_duplicado: bool
    alerta_legajo: bool
    alerta_empresa: bool = False
    linea_incompleta: bool
    conceptos: list[ConceptoAdicionalResponse] = []

    class Config:
        from_attributes = True


class LineaUpdateRequest(BaseModel):
    empresa_asignada: Optional[str] = None
    legajo_asignado: Optional[str] = None
    grupo_pago_aplicado: Optional[str] = None
    observacion: Optional[str] = None
    motivo_ajuste: Optional[str] = None


class ConceptoAdicionalRequest(BaseModel):
    descripcion: str
    tipo: TipoConcepto = TipoConcepto.OTRO
    importe: Decimal


class MensajeResponse(BaseModel):
    mensaje: str
    detalle: Optional[str] = None


class ValorHoraPulvRequest(BaseModel):
    # Valor hora de jornal de pulverización de la quincena (ADR-0007). None
    # limpia el valor (deja la comparación Tancadas vs Jornal sin dato).
    valor_hora_pulv: Optional[Decimal] = None


# ─── Maestro unificado de Conceptos ───────────────────────────────────────────

class ConceptoUnifResponse(BaseModel):
    id: int
    quincena: date
    tarea_nombre: str
    cliente_nombre: Optional[str] = None
    finca_nombre: Optional[str] = None
    codigo: Optional[int] = None
    unidad_base: UnidadBaseConcepto
    precio: Optional[Decimal] = None
    tipo: TipoConcepto
    heredado: bool = False
    # ADR-0008: categoría (1-7) de Mantenimiento mecánico. None = concepto
    # común (comportamiento actual, sin filtro por categoría).
    categoria: Optional[int] = None

    class Config:
        from_attributes = True


class ConceptoUnifRequest(BaseModel):
    quincena: date
    tarea_nombre: str
    cliente_nombre: Optional[str] = None   # NULL = común
    finca_nombre: Optional[str] = None
    codigo: Optional[int] = None
    unidad_base: UnidadBaseConcepto = UnidadBaseConcepto.FIJO
    precio: Optional[Decimal] = None
    tipo: TipoConcepto = TipoConcepto.OTRO
    categoria: Optional[int] = None


class ConceptoUnifUpdateRequest(BaseModel):
    codigo: Optional[int] = None
    unidad_base: Optional[UnidadBaseConcepto] = None
    precio: Optional[Decimal] = None
    tipo: Optional[TipoConcepto] = None
    categoria: Optional[int] = None


class ConceptoPorCodigoRequest(BaseModel):
    codigo: int


# ─── Categoría de operario (Mantenimiento mecánico, ADR-0008) ────────────────

class CategoriaOperarioRequest(BaseModel):
    cuil: str
    categoria: Optional[int] = None   # None = borra la asignación


class OperarioMantenimientoResponse(BaseModel):
    cuil: str
    nombre_empleado: Optional[str] = None
    legajo: Optional[str] = None
    categoria: Optional[int] = None