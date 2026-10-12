"""Schemas Pydantic (request/response) del módulo Facturación.

Los de la E1 salieron el 2026-10-12 con la pantalla Unidad de medida por
defecto. Los de acá son de la E2 (plan de la E2, sección 3.2): la entrada del
alta y la edición de Comprobantes, y las salidas del router de Comprobantes.

Los decimales salen como texto (`Decimal`, igual que en Terceros): un número
JSON pasaría por float y podría perder centavos.
"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class LineaEntrada(BaseModel):
    """Una Línea tal como la manda la pantalla.

    Los decimales entran como número o como texto con punto decimal (el front
    convierte el formato argentino antes de mandar). Que la cantidad sea > 0,
    el precio >= 0, la unidad una de las nueve y la tarea y la finca del
    maestro lo controla el servicio y no el schema: así el error sale como
    `linea_invalida` con la fila y el campo, que es lo que la pantalla usa
    para marcar la fila, y no como la lista genérica de FastAPI.

    Sin importe: lo calcula siempre el backend."""
    fecha: date
    tarea_id: int
    unidad: str
    finca_id: int | None = None
    cantidad: Decimal
    precio_unitario: Decimal


class ComprobanteEntrada(BaseModel):
    """La entrada de POST y PUT de un Comprobante.

    Empresa, número y fecha son opcionales acá y obligatorios en el servicio,
    por lo mismo que en la Línea: el faltante sale como `comprobante_invalido`
    con su campo. El tipo es texto por la misma razón."""
    tipo: str
    cliente_id: int
    empresa_emisora: str | None = None
    numero: str | None = None
    fecha: date | None = None
    # Obligatoria en una Nota de crédito; en una Factura tiene que ir vacía.
    factura_corregida_id: int | None = None
    # Sólo en el PUT: el `actualizado_en` tal como lo devolvió el detalle
    # (null si nunca se editó). Si ya no es el de la base, otra persona lo
    # guardó en el medio y el servicio responde `comprobante_modificado`
    # (pregunta 18). El alta lo ignora.
    actualizado_en: datetime | None = None
    lineas: list[LineaEntrada] = []


# ─── Salidas ────────────────────────────────────────────────────────────────
# Espejo de los dicts de ComprobantesService.listar() y .detalle().

class ComprobanteFila(BaseModel):
    """Una fila del listado de Comprobantes."""
    id: int
    tipo: str
    # Vacío sólo en un histórico sin número.
    numero: str | None = None
    # Vacía sólo en un histórico sin FECHA FAC.
    fecha: date | None = None
    # "AAAA-MM" de la primera Línea (pregunta 10).
    mes: str | None = None
    cliente_id: int
    cliente_nombre: str
    # Vacía sólo en un histórico.
    empresa_emisora: str | None = None
    es_historico: bool
    pendiente_de_facturar: bool
    cantidad_lineas: int
    cantidad_adjuntos: int
    # Con signo: negativo en una Nota de crédito.
    total_neto: Decimal


class ComprobanteReferencia(BaseModel):
    """La Factura que corrige una Nota de crédito, o una Nota de una Factura."""
    id: int
    numero: str | None = None
    fecha: date | None = None


class LineaSalida(BaseModel):
    id: int
    orden: int
    fecha: date
    tarea_id: int
    tarea_nombre: str
    unidad: str
    finca_id: int | None = None
    finca_nombre: str | None = None
    cantidad: Decimal
    precio_unitario: Decimal
    # Siempre positivo: el front lo muestra negativo en una Nota de crédito.
    importe: Decimal


class AdjuntoSalida(BaseModel):
    id: int
    nombre_original: str
    tipo_contenido: str
    tamano_bytes: int
    subido_en: datetime


class ComprobanteDetalle(ComprobanteFila):
    """Los campos de la fila, más lo que muestra la pantalla del Comprobante."""
    factura_corregida: ComprobanteReferencia | None = None
    notas_credito: list[ComprobanteReferencia] = []
    lineas: list[LineaSalida] = []
    adjuntos: list[AdjuntoSalida] = []
    creado_en: datetime | None = None
    # El PUT lo devuelve tal cual, sin zona horaria (pregunta 18).
    actualizado_en: datetime | None = None


class OpcionMaestro(BaseModel):
    """Un cliente o una finca del campo, para elegir en la pantalla."""
    id: int
    nombre: str


class TareaCampo(BaseModel):
    """Una tarea activa del campo, con lo que se lee de su descripción."""
    tarea_id: int
    nombre: str
    grupo_tarea: str | None = None
    # Una de las nueve claves, o None si la descripción no la define.
    unidad_sugerida: str | None = None
    no_facturable: bool
