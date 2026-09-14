"""Schemas Pydantic (request/response) del módulo Liquidación Terceros.

Etapa 2: los cuatro conjuntos de la quincena, de solo lectura. Son un espejo
del contrato de las consultas (`services/consulta_externa.py` y
`consulta_taller.py`): lo que llega de los orígenes, sin cálculo propio —
todavía no hay tarifas ni neto, eso empieza en la etapa 4.

Los campos opcionales lo son de verdad: un viaje puede no tener capataz
cargado, un repuesto puede no tener factura previa y quedarse sin precio.
Ninguno se rellena con un valor inventado; la pantalla los muestra vacíos para
que se vean.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class QuincenaResponse(BaseModel):
    """Una quincena elegible en el selector de las pantallas."""
    quincena: date          # su fecha de inicio: el 1 o el 16
    etiqueta: str           # '08-1Q', la notación del Excel de origen
    nombre: str             # '1ra de agosto 2026', para leer


class ViajeResponse(BaseModel):
    fecha_carga: str | None = None
    fecha_uso: str | None = None
    quincena_mes: str | None = None
    colectivo_nombre: str | None = None
    colectivo_patente: str | None = None
    colectivo_propiedad: str | None = None
    cliente: str | None = None
    finca: str | None = None
    nombre_tarea: str | None = None
    nombre_supervisor: str | None = None
    nombre_capataz: str | None = None
    nombre_chofer: str | None = None
    cantidadviajes: Decimal | None = None
    cantpersonas: int | None = None


class CargaCombustibleResponse(BaseModel):
    fecha_carga: str | None = None
    fecha_uso: str | None = None
    quincena_mes: str | None = None
    colectivo_nombre: str | None = None
    colectivo_patente: str | None = None
    colectivo_propiedad: str | None = None
    litros_cargados: Decimal | None = None
    vale: str | None = None
    origen_combustible: str | None = None
    usuario_carga: str | None = None


class RepuestoResponse(BaseModel):
    id_maquina: int | None = None
    maquina: str | None = None
    fecha: date | None = None
    # La de la descarga a la maquinaria. Hoy no se imputa por ella (ver
    # plan-terceros.md, sección 3); se muestra para que la diferencia esté a
    # la vista antes de la quincena de corte.
    fecha_descarga: date | None = None
    quincena_mes: str | None = None
    tipo_insumo: str | None = None
    rubro: str | None = None
    repuesto: str | None = None
    cantidad: Decimal | None = None
    precargas: Decimal | None = None
    monto_total: Decimal | None = None
    reparacion: str | None = None
    nombreprove: str | None = None
    propiedad_maquina: str | None = None


class HoraTallerResponse(BaseModel):
    fecha: date
    quincena_mes: str
    anio: int
    tercero: str
    maquina: str | None = None
    tipo_maquina: str | None = None
    rubro: str | None = None
    sub_rubro: str | None = None
    finca: str | None = None
    lugar: str | None = None
    estado: str | None = None
    horas: float
    horas_preparacion: float
    horas_traslado: float
    horas_total: float
    id_maquina: int | None = None


class EstadoHorasResponse(BaseModel):
    """Aprobadas, pendientes y rechazadas de la quincena.

    Es el tablero que pide el plan (sección 2.4): sirve para reclamarle al
    taller antes de liquidar, no después. Las rechazadas no aparecen en el
    listado de horas —no se cobran nunca— pero sí se cuentan acá.
    """
    aprobadas: int
    pendientes: int
    rechazadas: int
    horas_aprobadas: float
    horas_pendientes: float


class HorasTallerResponse(BaseModel):
    """El listado y el tablero juntos, en una sola respuesta.

    Van juntos porque salen de la misma lectura: el Sheet de la app del taller
    pesa 1,3 MB y tarda unos seis segundos en bajar. Separarlos en dos
    endpoints hacía que la portada del módulo lo bajara dos veces.
    """
    horas: list[HoraTallerResponse]
    estados: EstadoHorasResponse
