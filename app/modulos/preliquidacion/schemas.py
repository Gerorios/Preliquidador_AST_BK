from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from pydantic import AfterValidator, BaseModel, Field
from app.core.quincena import Quincena
from app.modulos.preliquidacion.models import TipoConcepto, UnidadBaseConcepto


class PreliquidacionGenerarRequest(BaseModel):
    quincena: Quincena  # día 1 o 16; otra fecha es 422 (ver app/core/quincena.py)


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
    # Propiedad de PreliquidacionLinea (no columna). Default False para que
    # cualquier otro constructor de LineaResponse no se rompa.
    mensualizado: bool = False
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
    # Solo lo llena copiar_quincena: cantidad de solapamientos por cliente
    # (CONTEXT-preliquidacion.md) que quedaron vigentes en la quincena destino tras copiar.
    solapamientos_heredados: Optional[int] = None


class ValorHoraPulvRequest(BaseModel):
    # Valor hora de jornal de pulverización de la quincena (ADR-0007). None
    # limpia el valor (deja la comparación Tancadas vs Jornal sin dato).
    valor_hora_pulv: Optional[Decimal] = None


class ValorHoraTractoristaRequest(BaseModel):
    # Valor hora del tractorista del control Plantas vs Jornal (el jornal
    # tractorista es este valor × 8). None limpia el valor (deja la
    # comparación contra jornal sin dato).
    valor_hora_tractorista: Optional[Decimal] = None


# ─── Maestro unificado de Conceptos ───────────────────────────────────────────

def _codigo_obligatorio(v):
    """ADR-0016: una regla del maestro no se guarda sin código. El ValueError
    en español sale tal cual en el 422 (convención de app/core/quincena.py)."""
    if v is None:
        raise ValueError("Ingresá el código del concepto")
    return v


def _precio_positivo(v):
    """ADR-0016: una regla del maestro no se guarda sin precio ni con precio <= 0."""
    if v is None:
        raise ValueError("Ingresá el precio del concepto")
    if v <= 0:
        raise ValueError("El precio tiene que ser mayor que 0")
    return v


# Son Optional a propósito: así el null explícito llega al validador y da el
# mensaje en español, en vez del error de tipo de Pydantic (en inglés).
CodigoObligatorio = Annotated[Optional[int], AfterValidator(_codigo_obligatorio)]
PrecioPositivo = Annotated[Optional[Decimal], AfterValidator(_precio_positivo)]


class ConceptoUnifResponse(BaseModel):
    id: int
    quincena: date
    tarea_nombre: str
    cliente_nombre: Optional[str] = None
    finca_nombre: Optional[str] = None
    # codigo y precio siguen Optional: puede haber reglas viejas incompletas (ADR-0016).
    codigo: Optional[int] = None
    unidad_base: UnidadBaseConcepto
    precio: Optional[Decimal] = None
    tipo: TipoConcepto
    heredado: bool = False
    # ADR-0008: categoría (1-12) de Mantenimiento mecánico. None = concepto
    # común (comportamiento actual, sin filtro por categoría).
    categoria: Optional[int] = None
    # ADR-0011: camino "por supervisor" — aplica a las líneas de esa tarea
    # cuyo nombre_supervisor coincida. Excluyente con cliente_nombre.
    supervisor_nombre: Optional[str] = None
    # WS11 / ADR-0011: tilde opcional de cualquier concepto NO común
    # (específico, por cliente o por supervisor). Si True, descarta SOLO los
    # comunes de la tarea para las líneas que matcheen esta regla (los
    # niveles no-comunes nunca se apagan entre sí). Default False =
    # comportamiento histórico (todos suman).
    reemplaza_comun: bool = False

    class Config:
        from_attributes = True


class ConceptoUnifRequest(BaseModel):
    quincena: Quincena
    tarea_nombre: str
    cliente_nombre: Optional[str] = None   # NULL = común (o por supervisor)
    finca_nombre: Optional[str] = None     # NULL con cliente = por cliente (cualquier finca)
    # ADR-0011: excluyente con cliente_nombre (422 si vienen ambos).
    supervisor_nombre: Optional[str] = None
    # ADR-0016: obligatorios. validate_default=True hace que "no vino" pase por
    # el mismo validador que "vino null" y dé el mismo mensaje en español (con
    # `int` a secas, Pydantic contestaría "Field required" en inglés).
    codigo: CodigoObligatorio = Field(default=None, validate_default=True)
    unidad_base: UnidadBaseConcepto = UnidadBaseConcepto.FIJO
    precio: PrecioPositivo = Field(default=None, validate_default=True)
    tipo: TipoConcepto = TipoConcepto.OTRO
    categoria: Optional[int] = Field(default=None, ge=1, le=12)
    # None = no lo mandaron: crear_concepto decide el default (True si NO es
    # común — específico, por cliente o por supervisor —, False si es común).
    # Si viene explícito (True/False) se respeta tal cual.
    reemplaza_comun: Optional[bool] = None
    # Solapamiento por cliente (CONTEXT-preliquidacion.md): si la regla que se crea SUMA a
    # reglas del eje cliente ya existentes (por cliente vs específicas del
    # mismo cliente), el POST responde 409 con el detalle salvo que el
    # liquidador lo confirme explícitamente con True.
    confirmar_solapamiento: bool = False


class ConceptoUnifUpdateRequest(BaseModel):
    # ADR-0016: SIN validate_default a propósito. Si el campo se omite, el
    # validador no corre y el PATCH sigue siendo parcial; si viene null o
    # <= 0, rechaza. Agregarle validate_default rompería la edición parcial.
    codigo: CodigoObligatorio = None
    unidad_base: Optional[UnidadBaseConcepto] = None
    precio: PrecioPositivo = None
    tipo: Optional[TipoConcepto] = None
    categoria: Optional[int] = Field(default=None, ge=1, le=12)
    supervisor_nombre: Optional[str] = None
    reemplaza_comun: Optional[bool] = None


class ConceptoPorCodigoRequest(BaseModel):
    codigo: int


class ConceptoPanelResponse(BaseModel):
    """Fila del panel de precios: todos los conceptos de una quincena (los 4
    caminos, ADR-0011), planos, con el precio de la quincena anterior para
    comparar."""
    id: int
    tarea_nombre: str
    # codigo y precio siguen Optional: puede haber reglas viejas incompletas (ADR-0016).
    codigo: Optional[int] = None
    cliente_nombre: Optional[str] = None
    finca_nombre: Optional[str] = None
    categoria: Optional[int] = None
    supervisor_nombre: Optional[str] = None
    unidad_base: UnidadBaseConcepto
    tipo: TipoConcepto
    precio: Optional[Decimal] = None
    heredado: bool = False
    reemplaza_comun: bool = False
    precio_anterior: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ConceptoPrecioMasivoRequest(BaseModel):
    ids: list[int]
    # ADR-0016: sigue obligatorio y además tiene que ser > 0.
    precio: Annotated[Decimal, AfterValidator(_precio_positivo)]


class ConceptoPrecioMasivoResponse(BaseModel):
    actualizados: int
    lineas_afectadas: int


# ─── Categoría de operario (Mantenimiento mecánico, ADR-0008) ────────────────

class CategoriaOperarioRequest(BaseModel):
    cuil: str
    categoria: Optional[int] = Field(default=None, ge=1, le=12)   # None = borra la asignación


class OperarioMantenimientoResponse(BaseModel):
    cuil: str
    nombre_empleado: Optional[str] = None
    legajo: Optional[str] = None
    categoria: Optional[int] = None