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
from datetime import date, datetime
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


class HoraServicioResponse(BaseModel):
    """Una máquina de un Tercero trabajando en una finca.

    Trae las dos medidas sobre las que se puede pactar —la hora de máquina y la
    cantidad que midió la tarea— porque cuál se paga lo decide la Unidad base de
    la tarifa, no el dato.
    """
    fecha: date
    quincena_mes: str
    planilla: str                    # de qué parte diario salió: COSECHA, MAQUINARIA, PULVERIZADA
    cliente: str | None = None
    finca: str | None = None
    tarea: str | None = None
    maquinaria: str | None = None
    # Sale del último campo de la descripción de la maquinaria. Viene vacío
    # cuando ahí hay una patente en vez de un nombre: el hueco se muestra, no se
    # rellena, porque liquidarle horas a una patente sería peor.
    tercero: str | None = None
    supervisor: str | None = None
    horas_maquina: Decimal
    # Cuánto midió la tarea y de qué son. Sólo la planilla de MAQUINARIA las
    # carga. `unidad` dice qué mide la tarea (BINS, TANCADAS, HORAS…) y **no**
    # cómo se paga: eso lo decide la Unidad base de la tarifa.
    unidades: Decimal | None = None
    unidad: str | None = None


class HoraReparacionResponse(BaseModel):
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


class HorasReparacionResponse(BaseModel):
    """El listado y el tablero juntos, en una sola respuesta.

    Van juntos porque salen de la misma lectura: el Sheet de la app del taller
    pesa 1,3 MB y tarda unos seis segundos en bajar. Separarlos en dos
    endpoints hacía que la portada del módulo lo bajara dos veces.
    """
    horas: list[HoraReparacionResponse]
    estados: EstadoHorasResponse


class AlertaResponse(BaseModel):
    """Una cosa que no cruza entre dos sistemas, y qué hacer con ella."""
    tipo: str
    severidad: str          # alta | media | baja
    sistema: str            # dónde se corrige, no dónde se detectó
    titulo: str
    detalle: str
    impacto: str | None = None      # por qué importa, en números
    referencias: list[str] = []     # 'compras:981', 'taller:990', 'campo:216'


class MaquinariaCampoResumen(BaseModel):
    """Cuánta maquinaria de terceros del sistema de campo se puede cruzar.

    Va como medición y no como una alerta por máquina porque la causa es una
    sola y no se arregla fila por fila: al sistema de campo le falta el dueño
    como campo propio.
    """
    total: int
    cruzan: int
    sin_patente: int
    con_patente_sin_par: int


class AlertasResponse(BaseModel):
    anio: int               # el año sobre el que se midió el movimiento
    alertas: list[AlertaResponse]
    maquinaria_campo: MaquinariaCampoResumen

# ─── La quincena generada (etapa 5) ─────────────────────────────────────────

class LiquidacionResponse(BaseModel):
    """Una quincena traída de los orígenes y guardada.

    Generar no congela nada: se puede volver a actualizar mientras el recibo no
    se haya emitido. `actualizada_en` en None significa que se generó y no se
    volvió a tocar.
    """
    id: int
    quincena: date
    generada_en: datetime
    actualizada_en: datetime | None = None
    filas: dict[str, int]          # cuántas quedaron por conjunto
    total_filas: int
    # Cuánto suma cada rubro, y el neto. Es lo que se mira para comparar una
    # quincena contra otra; la cantidad de filas no dice nada de eso.
    importes: dict[str, Decimal] = {}


class GenerarRequest(BaseModel):
    quincena: date


class DetalleConjunto(BaseModel):
    """Qué pasó con un conjunto al reconciliar."""
    origen: int            # cuántas filas tenía el origen
    insertadas: int
    borradas: int
    # Ya estaban, pero el origen les cambió algún dato que no es de la clave
    # —el dueño de un colectivo, por ejemplo—. Lo manual nunca se refresca.
    refrescadas: int = 0
    sin_cambios: int


class GenerarResponse(LiquidacionResponse):
    nueva: bool                            # False = era una actualización
    detalle: dict[str, DetalleConjunto]


# ─── El cálculo del neto (etapa 7) ──────────────────────────────────────────

class CalculoConjunto(BaseModel):
    """Qué pasó con un conjunto al ponerle precios."""
    hechos: int
    # Cuántos quedaron en cada estado. Los que no son CALCULADO no suman al
    # recibo y se resuelven con gente distinta según cuál sea.
    por_estado: dict[str, int]


class CalcularResponse(BaseModel):
    quincena: date
    calculada_en: datetime
    conjuntos: dict[str, CalculoConjunto]


class TotalTerceroResponse(BaseModel):
    """Lo que le queda a un tercero en una quincena.

    `total_a_facturar` **no lleva los seguros**: es la cifra que el Tercero
    copia en su factura, y el seguro no es algo que él le venda a la empresa
    sino una cuota que se le adelantó y se le recupera al pagarle. Recién
    `total_a_pagar` se la descuenta.

    En el recibo de la empresa el seguro va adentro del total a facturar, así
    que ahí la cifra a mostrar es `total_a_pagar` — es el mismo cálculo con los
    seguros en otro lugar, y las dos formas cierran en el mismo número.
    """
    tercero: str
    viajes: Decimal
    servicio: Decimal
    combustible: Decimal
    repuestos: Decimal
    reparacion: Decimal
    seguros: Decimal
    total_a_facturar: Decimal
    total_a_pagar: Decimal


class LineaGrillaResponse(BaseModel):
    """Una línea de la grilla de la quincena, venga del concepto que venga.

    Los seis conceptos se traducen a esta forma para poder mirarlos juntos. Lo
    que no aplica queda en null y la pantalla lo muestra vacío: un repuesto no
    tiene capataz, y rellenarlo con un guion haría que la exportación a Excel
    arrastre datos que nadie cargó.

    `importe` es siempre positivo; `signo` dice de qué lado del recibo cae.
    """
    concepto: str
    concepto_label: str
    signo: int                 # +1 se le paga, -1 se le descuenta
    id: int

    # Comunes a varios conceptos
    fecha: date | None = None
    tercero: str | None = None
    cliente: str | None = None
    finca: str | None = None
    capataz: str | None = None
    tarea: str | None = None

    # Propios de uno o dos conceptos. Van por separado y no armados en un
    # "detalle" porque una columna que diga "HIH521 · MEDINA, HECTOR · CORTO" no
    # se puede ordenar por patente ni filtrar por chofer.
    patente: str | None = None          # viajes, combustible
    chofer: str | None = None           # viajes
    tipo_viaje: str | None = None       # viajes — lo resuelve la tarifa
    vale: str | None = None             # combustible
    estacion: str | None = None         # combustible
    maquina: str | None = None          # servicio, repuestos, reparación
    planilla: str | None = None         # servicio
    supervisor: str | None = None       # servicio
    repuesto: str | None = None         # repuestos
    rubro: str | None = None            # repuestos, reparación
    sub_rubro: str | None = None        # reparación
    estado_taller: str | None = None    # reparación — no es el del cálculo
    sujeto: str | None = None           # seguros
    referencia: str | None = None       # seguros
    tipo_seguro: str | None = None      # seguros

    # El cálculo
    cantidad: Decimal | None = None
    unidad: str | None = None
    precio: Decimal | None = None
    importe: Decimal | None = None
    estado: str


# ─── El Tarifario (etapa 6) ─────────────────────────────────────────────────

class TarifaResponse(BaseModel):
    """Una regla del tarifario.

    Los cinco tarifarios comparten esta forma aunque no usen todos los campos:
    una tarifa de viaje no tiene `maquinaria` y un seguro no tiene `capataz`.
    Se devuelven en una sola forma para que la pantalla los trate igual; cuál
    corresponde a cada tipo lo dice `dimensiones`.
    """
    id: int
    quincena: date
    # Vino copiada de otra quincena y nadie la confirmó. Paga igual, pero se
    # resalta para no arrastrar un precio viejo si hubo aumento.
    heredada: bool
    creado_en: datetime
    # Cuántas dimensiones tiene cargadas: entre dos reglas que alcanzan al mismo
    # hecho, gana la de más.
    especificidad: int

    tercero: str | None = None
    cliente: str | None = None
    finca: str | None = None
    capataz: str | None = None
    tarea: str | None = None
    tipo_seguro: str | None = None
    sujeto: str | None = None
    referencia: str | None = None

    tipo_viaje: str | None = None
    unidad_base: str | None = None
    precio: Decimal | None = None
    importe: Decimal | None = None


class TarifaRequest(BaseModel):
    """Lo que se manda para crear o editar. Los campos que no apliquen al tipo
    se ignoran; los que falten y sean obligatorios devuelven 422 con el motivo."""
    tercero: str | None = None
    cliente: str | None = None
    finca: str | None = None
    capataz: str | None = None
    tarea: str | None = None
    tipo_seguro: str | None = None
    sujeto: str | None = None
    referencia: str | None = None
    tipo_viaje: str | None = None
    unidad_base: str | None = None
    precio: Decimal | None = None
    importe: Decimal | None = None


class CombinacionResponse(BaseModel):
    """Una combinación de dimensiones que la quincena tiene, con o sin precio.

    Sirve para dos cosas: saber qué falta pactar (`sin_precio` > 0) y ofrecer
    valores reales al cargar una regla, en vez de tipearlos. Un nombre tipeado a
    mano tiene que coincidir exacto con el del sistema de campo o la regla no
    alcanza a nada, y eso no se ve hasta que el recibo sale mal.

    `lineas` y `cantidad` son para priorizar: una combinación de 17 líneas y 140
    horas mueve el recibo mucho más que una de 1.
    """
    tercero: str | None = None
    cliente: str | None = None
    finca: str | None = None
    capataz: str | None = None
    tarea: str | None = None
    lineas: int
    cantidad: Decimal
    # Cuántas de esas líneas todavía no tienen precio.
    sin_precio: int = 0


class ConfirmarEnLoteRequest(BaseModel):
    """Varias reglas heredadas, dichas por una persona de una sola vez.

    Copiar una quincena trae doscientas reglas marcadas como heredadas.
    Confirmarlas de a una es exactamente el trabajo que copiar vino a evitar.
    """
    ids: list[int]


class ActualizarEnLoteRequest(BaseModel):
    """Un mismo valor para varias reglas a la vez.

    El caso real: el precio del viaje sube y hay que tocarlo en cuarenta reglas
    que no se diferencian en nada más.
    """
    ids: list[int]
    datos: dict


class TarifasEnLoteRequest(BaseModel):
    """Varias reglas del mismo tarifario, de una.

    Existe porque cargarlas de a una son cuarenta y cuatro requests y cuarenta y
    cuatro recálculos de la misma quincena para llegar al mismo resultado.
    """
    tarifas: list[dict]


class TarifasEnLoteResponse(BaseModel):
    cargadas: int
    # Las que no entraron, con el motivo. No se corta al primer error: si de
    # cuarenta y cuatro una está repetida, las otras cuarenta y tres tienen que
    # quedar cargadas igual.
    rechazadas: list[str]


class TarifarioResumen(BaseModel):
    cargadas: int
    heredadas: int          # cuántas están sin confirmar


class CopiarRequest(BaseModel):
    desde: date
    hasta: date
    # Vacío = los cinco tarifarios.
    tipos: list[str] | None = None


class CopiadoConjunto(BaseModel):
    en_origen: int
    copiadas: int
    ya_estaban: int         # no se pisan: el destino manda


class BienResponse(BaseModel):
    """Un colectivo o una máquina de un Tercero: lo que se le puede asegurar.

    Sale del sistema de campo, que es el maestro. Se ofrece como lista para que
    quien carga los seguros elija en vez de tipear: un nombre tipeado tiene que
    coincidir exacto con el del sistema o el seguro no se le imputa a nadie.
    """
    origen: str                  # 'colectivo' | 'maquinaria'
    id_origen: int
    # Vacío cuando el sistema de campo no lo trae. No se adivina: el hueco se
    # muestra para que alguien lo corrija en el origen.
    tercero: str | None = None
    nombre: str
    patente: str | None = None
    detalle: str | None = None   # marca o tipo, para reconocerlo

