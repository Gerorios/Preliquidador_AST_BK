"""Endpoints del módulo Liquidación Terceros.

Todo **de solo lectura**: no hay POST ni PATCH y no se escribe en ninguna base.
El módulo no tiene tablas propias hasta la etapa 4 de su plan; cada pedido va a
los orígenes y devuelve lo que hay.

Dos cosas distintas conviven acá:

  - Los cuatro **conjuntos de una quincena** (etapa 2): viajes, combustible,
    repuestos y horas de taller. Llevan `?quincena=`.
  - Las **alertas de cruce** (etapa 3): lo que no se encuentra entre los tres
    sistemas de origen. No llevan quincena, porque un problema de cruce es del
    maestro y no de un período.

Un endpoint por conjunto y **ninguno que los junte**. Hubo uno —un `/resumen`
que devolvía las cuatro cifras de la portada— y se sacó: pedía los cuatro
orígenes en serie y tardaba 15 segundos, que es lo primero que el liquidador
ve al entrar. Con cuatro endpoints el navegador los pide en paralelo, cada
tarjeta aparece cuando llega la suya, el que falla no voltea a los demás, y al
abrir la pantalla del conjunto los datos ya están en caché. El precio es que la
portada trae las filas para contar cuatro números; a este volumen sale más
barato que esperar.

Los listados devuelven la quincena entera sin paginar: son cientos de filas
(756 viajes en la quincena más cargada de 2026) y el liquidador trabaja mirando
el conjunto. Filtrar y ordenar es tarea de la pantalla, que ya las tiene.
"""
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_usuario_actual
from app.core.database import get_db_externa, get_db_propia, get_db_sueldos
from app.modulos.terceros.permisos import requiere_operativo
from app.modulos.terceros.schemas import (
    AlertasResponse,
    BienResponse,
    CalcularResponse,
    CargaCombustibleResponse,
    ActualizarEnLoteRequest,
    CombinacionResponse,
    ConfirmarEnLoteRequest,
    CargaSinEstacion,
    CruceResponse,
    FilaComparada,
    EstacionResponse,
    LineaFacturada,
    LineasAManoRequest,
    OrigenRequest,
    SubidaResponse,
    FuenteVerificada,
    LineaGrillaResponse,
    CopiadoConjunto,
    CopiarRequest,
    GenerarRequest,
    GenerarResponse,
    LiquidacionResponse,
    HoraServicioResponse,
    HorasReparacionResponse,
    QuincenaResponse,
    RepuestoResponse,
    TarifaRequest,
    TarifaResponse,
    TarifarioResumen,
    TarifasEnLoteRequest,
    TarifasEnLoteResponse,
    TotalTerceroResponse,
    ViajeResponse,
)
from app.modulos.terceros.services import alertas_cruce, quincenas
from app.modulos.terceros.services.calculo_service import (
    CalculoService, LiquidacionInexistente,
)
from app.modulos.terceros.services.consulta_externa import ConsultaExternaService
from app.modulos.terceros.services.estaciones_service import (
    ArchivoInvalido, EstacionesService, patente_de,
)
from app.modulos.terceros.services.grilla_service import GrillaService
from app.modulos.terceros.services.verificaciones_service import VerificacionesService
from app.modulos.terceros.services.liquidacion_service import LiquidacionService
from app.modulos.terceros.services.tarifario_service import (
    TIPOS as TIPOS_TARIFA, TarifaInvalida, TarifarioService, especificidad,
)
from app.modulos.terceros.services.consulta_taller import (
    ConsultaTallerService,
    TallerNoConfigurado,
)

# Lo que puede fallar al leer un origen sin que sea un error de programación:
# falta de configuración, el Sheet que no contesta, o el Sheet que cambió de
# formato (ValueError de `_filas`). Se listan a propósito en vez de atrapar
# Exception: un TypeError nuestro tiene que romper fuerte, no disfrazarse de
# "el origen no anda".
FALLAS_DE_ORIGEN = (TallerNoConfigurado, httpx.HTTPError, ValueError)

router = APIRouter(
    prefix="/api/terceros",
    tags=["Liquidación Terceros"],
    dependencies=[Depends(requiere_operativo)],
)


def _mensaje_origen(e: Exception) -> str:
    """Un error de origen se cuenta como lo que es, no como "error interno".

    Quien lo lee es el liquidador, y puede hacer algo distinto según el caso:
    si falta la URL es configuración y la resuelve Gero; si el Sheet no
    contesta, se reintenta más tarde; si cambió de formato, hay que ajustar la
    consulta."""
    if isinstance(e, TallerNoConfigurado):
        return ("Falta configurar la dirección del Sheet de la app del taller "
                "(TALLER_SHEET_URL). Las horas de taller no se pueden leer hasta que esté.")
    if isinstance(e, httpx.HTTPError):
        return f"El Sheet de la app del taller no respondió: {e}"
    return str(e)


def quincena_param(
    quincena: date = Query(..., description="Primer día de la quincena: el 1 o el 16"),
) -> date:
    if not quincenas.es_inicio_valido(quincena):
        raise HTTPException(
            status_code=422,
            detail="Una quincena se identifica por su primer día: el 1 o el 16 del mes.",
        )
    return quincena


def get_consulta_externa(
    db_externa: Session = Depends(get_db_externa),
    db_sueldos: Session = Depends(get_db_sueldos),
) -> ConsultaExternaService:
    return ConsultaExternaService(db_externa, db_sueldos)


def get_consulta_taller() -> ConsultaTallerService:
    return ConsultaTallerService()


def get_tarifario(
    db_propia: Session = Depends(get_db_propia),
) -> TarifarioService:
    return TarifarioService(db_propia)


def _tarifa_a_dict(fila) -> dict:
    """La forma común de las cinco tablas, más su especificidad."""
    campos = ("tercero", "cliente", "finca", "capataz", "tarea",
              "tipo_seguro", "sujeto", "referencia",
              "tipo_viaje", "unidad_base", "precio", "importe")
    salida = {c: getattr(fila, c, None) for c in campos}
    # Una dimensión vacía se guarda como '' para que el índice único funcione,
    # pero hacia afuera es "no aplica": se devuelve como null.
    for d in fila.DIMENSIONES:
        if salida.get(d) == "":
            salida[d] = None
    salida.update(id=fila.id, quincena=fila.quincena, heredada=fila.heredada,
                  creado_en=fila.creado_en, especificidad=especificidad(fila))
    return salida


def get_calculo(
    db_propia: Session = Depends(get_db_propia),
) -> CalculoService:
    return CalculoService(db_propia)


# Qué concepto de la grilla toca cada tarifario. Los seguros no están porque no
# tienen hechos: la tarifa **es** la línea, así que cargarla ya es el resultado
# y no hay nada que recalcular.
CONCEPTO_DEL_TARIFARIO = {
    "viajes": "viajes",
    "servicio": "servicio",
    "combustible": "combustible",
    "reparacion": "reparacion",
}


def recalcular_tras_el_precio(db: Session, tipo: str, quincena: date | None) -> None:
    """Cargar un precio ya lo aplica. No hay botón de recalcular.

    Es la misma mecánica que Preliquidación usa con sus conceptos: el precio se
    guarda y en el mismo request se recalcula lo que ese precio alcanza. Un
    botón aparte deja a la pantalla mostrando números viejos hasta que alguien
    se acuerde de apretarlo, y nadie se acuerda.

    Se recalcula **sólo el concepto de ese tarifario**: tocar la tarifa de un
    viaje no puede cambiar lo que vale un repuesto.
    """
    concepto = CONCEPTO_DEL_TARIFARIO.get(tipo)
    if concepto is None or quincena is None:
        return
    CalculoService(db).recalcular_si_existe(quincena, (concepto,))


def get_grilla(
    db_propia: Session = Depends(get_db_propia),
) -> GrillaService:
    return GrillaService(db_propia)


def get_verificaciones(
    db_propia: Session = Depends(get_db_propia),
) -> VerificacionesService:
    return VerificacionesService(db_propia)


def get_estaciones(
    db_propia: Session = Depends(get_db_propia),
) -> EstacionesService:
    return EstacionesService(db_propia)


def _facturada_a_dict(f) -> dict:
    return {
        "id": f.id, "estacion": f.estacion.nombre if f.estacion else "",
        "fecha": f.fecha, "vale": f.vale, "litros": f.litros,
        "importe": f.importe, "producto": f.producto,
        "patente": f.patente, "chofer": f.chofer,
    }


def _carga_a_dict(c) -> dict:
    return {
        "id": c.id, "estacion": c.origen, "fecha": c.fecha_uso,
        "vale": c.vale, "litros": c.litros, "patente": c.colectivo_patente,
        "tercero": c.tercero, "observacion": c.observacion,
    }


def _patentes_de_colectivos(externa) -> set[str] | None:
    """Las patentes del maestro del sistema de campo.

    Separan lo que falta cargar de lo que nunca iba a estar: la cisterna, los
    bidones y las camionetas no se cargan como flete y no le corresponden a
    ningún tercero.

    Si el maestro no contesta se cruza igual, pero la lista de "falta cargar"
    va a traer cosas que no son de nadie. Es mejor que no mostrar nada.
    """
    try:
        patentes = {patente_de(c.get("patente")) for c in externa.colectivos_campo()}
        patentes.discard(None)
        return patentes
    except FALLAS_DE_ORIGEN:
        return None


def get_liquidacion(
    db_propia: Session = Depends(get_db_propia),
    externa: ConsultaExternaService = Depends(get_consulta_externa),
    taller: ConsultaTallerService = Depends(get_consulta_taller),
) -> LiquidacionService:
    return LiquidacionService(db_propia, externa, taller)


@router.get("/")
def estado():
    return {"modulo": "terceros", "estado": "en construcción"}


@router.get("/liquidaciones", response_model=list[LiquidacionResponse])
def listar_liquidaciones(
    servicio: LiquidacionService = Depends(get_liquidacion),
    calculo: CalculoService = Depends(get_calculo),
):
    """Las quincenas ya generadas, de la más nueva a la más vieja, con lo que
    suma cada rubro.

    Los importes se traen de una sola pasada para todas las quincenas: pedirlos
    quincena por quincena serían seis consultas por fila de la tabla.
    """
    importes = calculo.importes_por_quincena()
    return [{**fila, "importes": importes.get(fila["quincena"], {})}
            for fila in servicio.listar()]


@router.post("/liquidaciones/generar", response_model=GenerarResponse)
def generar_liquidacion(
    req: GenerarRequest,
    usuario=Depends(get_usuario_actual),
    servicio: LiquidacionService = Depends(get_liquidacion),
    calculo: CalculoService = Depends(get_calculo),
):
    """Trae las cinco fuentes de esa quincena, las guarda y les pone precio.

    Si la quincena ya existe **no la rehace**: reconcilia. Suma lo que apareció
    en el origen, saca lo que ya no está, y deja donde está lo que el liquidador
    cargó a mano. Por eso se puede apretar todas las veces que haga falta
    mientras el recibo no esté emitido.

    Tarda: son dos bases y un Google Sheet. La lentitud es de una sola vez, no
    de cada pantalla, que es justamente para lo que sirve guardar.
    """
    if not quincenas.es_inicio_valido(req.quincena):
        raise HTTPException(
            status_code=422,
            detail="Una quincena se identifica por su primer día: el 1 o el 16 del mes.",
        )
    try:
        salida = servicio.generar(req.quincena, usuario_id=getattr(usuario, "id", None))
    except FALLAS_DE_ORIGEN as e:
        # Si un origen no contesta, no se guarda media quincena.
        raise HTTPException(status_code=502, detail=_mensaje_origen(e))
    # Generar deja la quincena con los precios ya puestos. Sin esto el
    # liquidador ve una pantalla de ceros y no sabe si es que no hay tarifas o
    # que le falta apretar algo. Al lado de traer cinco orígenes, no se nota.
    calculo.calcular(req.quincena)
    return salida


@router.post("/liquidaciones/calcular", response_model=CalcularResponse)
def calcular_liquidacion(
    req: GenerarRequest,
    servicio: CalculoService = Depends(get_calculo),
):
    """Le aplica a cada hecho de la quincena la tarifa que le corresponde.

    Se corre sola al generar, y a mano cada vez que se cargan o se corrigen
    tarifas. Es idempetente: vuelve a mirar todo y reescribe el resultado, así
    que apretarla de más no rompe nada.

    Lo que queda sin precio **no vale cero**: queda con un estado que dice por
    qué, y esos estados se consultan en `/liquidaciones/pendientes`.
    """
    try:
        conjuntos = servicio.calcular(req.quincena)
    except LiquidacionInexistente as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"quincena": req.quincena,
            "calculada_en": datetime.now(),
            "conjuntos": conjuntos}


@router.get("/liquidaciones/lineas", response_model=list[LineaGrillaResponse])
def lineas_de_la_quincena(
    quincena: date = Depends(quincena_param),
    servicio: GrillaService = Depends(get_grilla),
):
    """Los seis conceptos de la quincena en una sola lista.

    Vienen todas las líneas, también las que quedaron sin importe: son
    justamente las que hay que resolver, y esconderlas del listado sería
    esconder el trabajo pendiente.

    No recalcula: devuelve lo que quedó guardado. Si sale todo en cero es que la
    quincena no se calculó, y eso se arregla en `/liquidaciones/calcular`.
    """
    return servicio.lineas(quincena)


@router.get("/liquidaciones/totales", response_model=list[TotalTerceroResponse])
def totales_de_la_quincena(
    quincena: date = Depends(quincena_param),
    servicio: CalculoService = Depends(get_calculo),
):
    """Por tercero: el Total a facturar y el Total a pagar de esa quincena.

    Sólo suma lo que tiene precio. Un hecho sin tarifa no entra como cero:
    directamente no entra, y aparece en `/liquidaciones/pendientes`.
    """
    return servicio.totales(quincena)


@router.get("/liquidaciones/pendientes", response_model=dict[str, dict[str, int]])
def pendientes_de_la_quincena(
    quincena: date = Depends(quincena_param),
    servicio: CalculoService = Depends(get_calculo),
):
    """Qué falta para poder liquidar, contado por concepto y por motivo.

    Cada motivo se resuelve con alguien distinto —SIN_TERCERO lo arregla el
    sistema de campo, SIN_TARIFA lo carga el liquidador, NO_APROBADA la aprueba
    el taller—, así que se cuentan por separado y no como un total.
    """
    return servicio.pendientes(quincena)


@router.get("/bienes", response_model=list[BienResponse])
def listar_bienes(
    servicio: ConsultaExternaService = Depends(get_consulta_externa),
):
    """Los colectivos y la maquinaria de los terceros: lo que se asegura.

    No lleva quincena: es el padrón del sistema de campo, no un movimiento. Lo
    consume la pantalla de seguros, para que quien los carga elija de la lista
    y el nombre coincida siempre con el que el módulo conoce.
    """
    return servicio.bienes_terceros()


# ─── El Tarifario ───────────────────────────────────────────────────────────
#
# Un solo juego de endpoints para los cinco tarifarios: cambia el `tipo` de la
# ruta. Las cinco tablas tienen dimensiones distintas pero el mismo circuito —
# cargar, editar, confirmar, borrar y copiar de otra quincena—, así que cinco
# juegos de endpoints iguales serían cinco lugares donde arreglar el mismo bug.

@router.get("/tarifario/resumen", response_model=dict[str, TarifarioResumen])
def resumen_tarifario(
    quincena: date = Depends(quincena_param),
    servicio: TarifarioService = Depends(get_tarifario),
):
    """Cuántas reglas tiene cada tarifario y cuántas están sin confirmar."""
    return servicio.resumen(quincena)


@router.post("/tarifario/copiar", response_model=dict[str, CopiadoConjunto])
def copiar_tarifario(
    req: CopiarRequest,
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    """Trae las reglas de otra quincena, marcadas como heredadas.

    Lo que ya exista en el destino **no se toca**: copiar es traer lo que falta,
    nunca pisar un precio que alguien ya pactó para esta quincena.
    """
    for q in (req.desde, req.hasta):
        if not quincenas.es_inicio_valido(q):
            raise HTTPException(
                status_code=422,
                detail="Una quincena se identifica por su primer día: el 1 o el 16 del mes.")
    tipos = tuple(req.tipos) if req.tipos else None
    try:
        detalle = servicio.copiar(req.desde, req.hasta, tipos)
    except TarifaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
    for tipo in (tipos or tuple(CONCEPTO_DEL_TARIFARIO)):
        recalcular_tras_el_precio(db_propia, tipo, req.hasta)
    return detalle


@router.post("/tarifario/{tipo}/lote", response_model=TarifasEnLoteResponse)
def crear_tarifas_en_lote(
    tipo: str,
    req: TarifasEnLoteRequest,
    quincena: date = Depends(quincena_param),
    usuario=Depends(get_usuario_actual),
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    """Carga varias reglas de un tarifario y recalcula **una sola vez**.

    De a una, pactar las cuarenta y cuatro combinaciones de horas de servicio de
    una quincena son cuarenta y cuatro requests y cuarenta y cuatro recálculos
    de lo mismo.

    No se corta al primer error: lo que no entra se devuelve con su motivo y el
    resto queda cargado. Cortar obligaría a adivinar cuáles alcanzaron a
    guardarse antes de la que falló.
    """
    cargadas, rechazadas = 0, []
    for datos in req.tarifas:
        try:
            servicio.crear(tipo, quincena, datos,
                           usuario_id=getattr(usuario, "id", None))
            cargadas += 1
        except TarifaInvalida as e:
            rechazadas.append(str(e))
    if cargadas:
        recalcular_tras_el_precio(db_propia, tipo, quincena)
    return {"cargadas": cargadas, "rechazadas": rechazadas}


@router.get("/tarifario/{tipo}/combinaciones", response_model=list[CombinacionResponse])
def combinaciones_de_la_quincena(
    tipo: str,
    quincena: date = Depends(quincena_param),
    servicio: CalculoService = Depends(get_calculo),
):
    """Las combinaciones que la quincena tiene, con o sin precio.

    De acá salen dos cosas: la lista de lo que falta pactar —las que tienen
    `sin_precio` > 0— y los valores que la pantalla ofrece al cargar una regla,
    para no tipear un nombre que tiene que coincidir exacto con el del sistema
    de campo.

    De la que más líneas alcanza a la que menos, que es el orden en que conviene
    pactarlas: la primera mueve el recibo mucho más que la última.
    """
    return servicio.combinaciones(tipo, quincena)


@router.get("/tarifario/{tipo}", response_model=list[TarifaResponse])
def listar_tarifas(
    tipo: str,
    quincena: date = Depends(quincena_param),
    servicio: TarifarioService = Depends(get_tarifario),
):
    """Las reglas de ese tarifario, de la más general a la más específica."""
    try:
        return [_tarifa_a_dict(f) for f in servicio.listar(tipo, quincena)]
    except TarifaInvalida as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tarifario/{tipo}", response_model=TarifaResponse, status_code=201)
def crear_tarifa(
    tipo: str,
    req: TarifaRequest,
    quincena: date = Depends(quincena_param),
    usuario=Depends(get_usuario_actual),
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    try:
        fila = servicio.crear(tipo, quincena, req.model_dump(exclude_none=True),
                              usuario_id=getattr(usuario, "id", None))
    except TarifaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
    recalcular_tras_el_precio(db_propia, tipo, quincena)
    return _tarifa_a_dict(fila)


@router.patch("/tarifario/{tipo}/lote", response_model=TarifasEnLoteResponse)
def actualizar_tarifas_en_lote(
    tipo: str,
    req: ActualizarEnLoteRequest,
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    """El mismo valor para varias reglas, y un solo recálculo.

    Es lo que se usa cuando sube el precio del viaje: se filtra a quiénes
    alcanza y se les cambia el número de una, en vez de abrir cuarenta reglas.
    """
    actualizadas, rechazadas, quincena = 0, [], None
    for id_ in req.ids:
        try:
            fila = servicio.actualizar(tipo, id_, req.datos)
            quincena = fila.quincena
            actualizadas += 1
        except TarifaInvalida as e:
            rechazadas.append(str(e))
    recalcular_tras_el_precio(db_propia, tipo, quincena)
    return {"cargadas": actualizadas, "rechazadas": rechazadas}


@router.patch("/tarifario/{tipo}/{id_}", response_model=TarifaResponse)
def actualizar_tarifa(
    tipo: str,
    id_: int,
    req: TarifaRequest,
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    """Cambiar un precio **confirma** la regla: si estaba heredada deja de
    estarlo, porque alguien la miró y decidió."""
    try:
        fila = servicio.actualizar(tipo, id_, req.model_dump(exclude_none=True))
    except TarifaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
    recalcular_tras_el_precio(db_propia, tipo, fila.quincena)
    return _tarifa_a_dict(fila)


@router.post("/tarifario/{tipo}/confirmar-lote", response_model=TarifasEnLoteResponse)
def confirmar_tarifas_en_lote(
    tipo: str,
    req: ConfirmarEnLoteRequest,
    servicio: TarifarioService = Depends(get_tarifario),
):
    """Les saca la marca de heredada a varias reglas de una.

    Copiar de otra quincena trae doscientas reglas sin confirmar; ir una por
    una es el trabajo que copiar vino a evitar. Se filtra lo que se quiere dar
    por bueno y se confirma junto.

    No recalcula: confirmar no cambia ningún precio, sólo dice que alguien lo
    miró.
    """
    confirmadas, rechazadas = 0, []
    for id_ in req.ids:
        try:
            servicio.confirmar(tipo, id_)
            confirmadas += 1
        except TarifaInvalida as e:
            rechazadas.append(str(e))
    return {"cargadas": confirmadas, "rechazadas": rechazadas}


@router.post("/tarifario/{tipo}/{id_}/confirmar", response_model=TarifaResponse)
def confirmar_tarifa(
    tipo: str,
    id_: int,
    servicio: TarifarioService = Depends(get_tarifario),
):
    """Dejar el precio como está, pero dicho por una persona.

    No recalcula: el número no cambió, sólo se le sacó la marca de heredada."""
    try:
        return _tarifa_a_dict(servicio.confirmar(tipo, id_))
    except TarifaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/tarifario/{tipo}/{id_}", status_code=204)
def eliminar_tarifa(
    tipo: str,
    id_: int,
    servicio: TarifarioService = Depends(get_tarifario),
    db_propia: Session = Depends(get_db_propia),
):
    """Borrar una tarifa deja sin precio a los hechos que alcanzaba, así que
    hay que recalcular: si no, seguirían mostrando un importe que ya nadie
    puede explicar de dónde sale."""
    try:
        quincena = servicio.quincena_de(tipo, id_)
        servicio.eliminar(tipo, id_)
    except TarifaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
    recalcular_tras_el_precio(db_propia, tipo, quincena)


@router.get("/quincenas", response_model=list[QuincenaResponse])
def listar_quincenas(
    cantidad: int = Query(24, ge=1, le=48, description="Cuántas traer, de la más nueva a la más vieja"),
):
    """Las quincenas elegibles del selector. Se calculan por calendario."""
    return [
        QuincenaResponse(
            quincena=q, etiqueta=quincenas.etiqueta(q), nombre=quincenas.nombre(q)
        )
        for q in quincenas.recientes(cantidad=cantidad)
    ]


@router.get("/viajes", response_model=list[ViajeResponse])
def listar_viajes(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaExternaService = Depends(get_consulta_externa),
):
    return servicio.viajes(quincena)


@router.get("/combustible", response_model=list[CargaCombustibleResponse])
def listar_combustible(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaExternaService = Depends(get_consulta_externa),
):
    return servicio.cargas_combustible(quincena)


@router.get("/repuestos", response_model=list[RepuestoResponse])
def listar_repuestos(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaExternaService = Depends(get_consulta_externa),
):
    return servicio.repuestos(quincena)


@router.get("/horas-servicio", response_model=list[HoraServicioResponse])
def listar_horas_servicio(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaExternaService = Depends(get_consulta_externa),
):
    """Las horas que la maquinaria de los Terceros trabajó en las fincas.

    Es lo que se les **paga** por el servicio de maquinaria. Salen de tres
    partes diarios distintos del sistema de campo —cosecha, maquinaria y
    pulverizadas— y vienen con las dos medidas sobre las que se puede pactar:
    la hora de máquina y la cantidad que midió la tarea. Cuál de las dos se
    paga lo decide la Unidad base de la tarifa, no el dato.
    """
    return servicio.horas_servicio(quincena)


@router.get("/horas-reparacion", response_model=HorasReparacionResponse)
def listar_horas_reparacion(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaTallerService = Depends(get_consulta_taller),
):
    """Las horas de reparación cobrables de la quincena, más el recuento por estado.

    Son las que el taller de la empresa le dedicó a la máquina del Tercero: se
    le **descuentan**. No confundir con las Horas de servicio, que son su
    máquina trabajando para nosotros y se le pagan.

    `horas` trae las aprobadas y las pendientes; las rechazadas no están porque
    no se cobran nunca. `estados` las cuenta a las tres: sirve para reclamarle
    al taller **antes** de liquidar, porque una hora que quede pendiente cuando
    se emita el recibo es plata que no se factura en esta quincena.

    Las dos cosas vienen juntas porque salen de la misma lectura del Sheet, que
    tarda unos seis segundos: pedirlas por separado lo bajaba dos veces.
    """
    try:
        return HorasReparacionResponse(
            horas=servicio.horas_quincena(quincena),
            estados=servicio.estados_quincena(quincena),
        )
    except FALLAS_DE_ORIGEN as e:
        raise HTTPException(status_code=502, detail=_mensaje_origen(e))


@router.get("/estaciones", response_model=list[EstacionResponse])
def listar_estaciones(
    quincena: date = Depends(quincena_param),
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Las estaciones y cuánto tienen cargado de esa quincena."""
    cargadas = servicio.lineas_por_estacion(quincena)
    return [{
        "id": e.id, "nombre": e.nombre, "origen_campo": e.origen_campo,
        "acepta_archivo": e.mapeo is not None, "activa": bool(e.activa),
        "lineas": cargadas.get(e.id, 0),
    } for e in servicio.listar()]


@router.post("/estaciones/{id_}/subir", response_model=SubidaResponse)
def subir_archivo_de_estacion(
    id_: int,
    quincena: date = Form(...),
    archivo: UploadFile = File(...),
    usuario=Depends(get_usuario_actual),
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Carga lo que facturó una estación.

    Cada línea va a la quincena de **su** fecha, no a la del formulario: el
    reporte de una estación puede arrancar el 1 y terminar el 19. La quincena
    del formulario es el respaldo para las líneas que vengan sin fecha.

    Subir dos veces no acumula: reemplaza lo que esa estación tenía en las
    quincenas que el archivo toca.
    """
    if not quincenas.es_inicio_valido(quincena):
        raise HTTPException(
            status_code=422,
            detail="Una quincena se identifica por su primer día: el 1 o el 16 del mes.")
    try:
        return servicio.subir(id_, quincena, archivo.file.read(),
                              archivo.filename or "",
                              usuario_id=getattr(usuario, "id", None))
    except ArchivoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/estaciones/{id_}/lineas", response_model=list[LineaFacturada])
def lineas_de_una_estacion(
    id_: int,
    quincena: date = Depends(quincena_param),
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Lo que esa estación tiene cargado de esa quincena."""
    return [_facturada_a_dict(f) for f in servicio.lineas_de(id_, quincena)]


@router.post("/estaciones/{id_}/lineas", status_code=201)
def cargar_lineas_a_mano(
    id_: int,
    req: LineasAManoRequest,
    usuario=Depends(get_usuario_actual),
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Carga remitos tipeados, para la estación que no manda archivo.

    A diferencia de subir un archivo, esto **suma**: se tipea de a poco, a
    medida que llegan las fotos, y borrar lo anterior en cada carga sería
    perder lo que alguien acaba de escribir.
    """
    try:
        n = servicio.agregar_a_mano(
            id_, [l.model_dump() for l in req.lineas],
            usuario_id=getattr(usuario, "id", None))
    except ArchivoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"cargadas": n}


@router.delete("/estaciones/lineas/{id_}", status_code=204)
def borrar_linea_facturada(
    id_: int,
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Sacar una línea tipeada mal. Las que vienen de un archivo se corrigen
    volviendo a subirlo; una tipeada no tiene de dónde volver a salir."""
    try:
        servicio.borrar_linea(id_)
    except ArchivoInvalido as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/estaciones/{id_}", response_model=EstacionResponse)
def definir_origen_de_estacion(
    id_: int,
    req: OrigenRequest,
    servicio: EstacionesService = Depends(get_estaciones),
):
    """Con qué nombre se registran sus cargas en el sistema de campo.

    Sin esto no hay nada que cruzar, y no se puede adivinar: el archivo se
    llama «Calchaqui» y esa estación en el sistema de campo es
    `YPF OASIS ALDERETE`.
    """
    try:
        e = servicio.definir_origen(id_, req.origen_campo)
    except ArchivoInvalido as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    return {"id": e.id, "nombre": e.nombre, "origen_campo": e.origen_campo,
            "acepta_archivo": e.mapeo is not None, "activa": bool(e.activa),
            "lineas": 0}


@router.get("/estaciones/cruce", response_model=CruceResponse)
def cruce_con_las_estaciones(
    quincena: date = Depends(quincena_param),
    servicio: EstacionesService = Depends(get_estaciones),
    externa: ConsultaExternaService = Depends(get_consulta_externa),
):
    """Lo que la estación facturó contra lo que se cargó, línea por línea.

    Viene todo junto y con el estado en cada fila: mirar una estación, o mirar
    sólo lo que no cruzó, es filtrar la misma lista.

    Las patentes del maestro del sistema de campo se usan para separar lo que
    falta cargar de lo que nunca iba a estar: la cisterna, los bidones y las
    camionetas no se cargan como flete y no le corresponden a ningún tercero.
    """
    c = servicio.cruce(quincena, _patentes_de_colectivos(externa))
    return {
        "facturadas": c["facturadas"], "cargadas": c["cargadas"],
        "cruzan": c["cruzan"],
        "por_vale": c["por_vale"], "por_huella": c["por_huella"],
        "por_parecida": c["por_parecida"],
        "filas": [{
            "estado": f["estado"],
            "estacion_id": f["estacion_id"],
            "facturada": _facturada_a_dict(f["facturada"]) if f["facturada"] else None,
            "carga": _carga_a_dict(f["carga"]) if f["carga"] else None,
        } for f in c["filas"]],
    }


@router.get("/verificaciones", response_model=list[FuenteVerificada])
def verificaciones_de_la_quincena(
    quincena: date = Depends(quincena_param),
    servicio: VerificacionesService = Depends(get_verificaciones),
):
    """Lo que hay que mirar antes de liquidar, agrupado por fuente.

    Por fuente y no por tipo de problema: cada fuente la corrige alguien
    distinto, y una lista de "duplicados" mezcla tres conversaciones con tres
    personas.

    Se mide sobre lo guardado, que es lo que se va a cobrar. Si alguien arregló
    el origen y la quincena todavía no se actualizó, la verificación sigue
    apareciendo — y tiene que aparecer.
    """
    return servicio.por_fuente(quincena)


@router.get("/alertas", response_model=AlertasResponse)
def alertas_de_cruce(
    anio: int = Query(default_factory=lambda: date.today().year, ge=2020, le=2100,
                      description="Año sobre el que se mide si una máquina tuvo movimiento"),
    externa: ConsultaExternaService = Depends(get_consulta_externa),
    taller: ConsultaTallerService = Depends(get_consulta_taller),
):
    """Lo que no cruza entre los tres sistemas de origen.

    No lleva quincena: un problema de cruce es del maestro, no de un período.
    El año sí, y sólo para una cosa: saber si una máquina descolgada tuvo
    movimiento, que es lo que distingue una alerta accionable de una fila
    muerta.

    Si la app del taller no contesta, no se devuelve media verdad: sin su
    maestro, la mitad de las alertas serían falsas —toda máquina parecería no
    tener par—, así que se responde 502 y se dice por qué.
    """
    try:
        maquinas_taller = taller.maestro()
    except FALLAS_DE_ORIGEN as e:
        raise HTTPException(status_code=502, detail=_mensaje_origen(e))

    maquinas_compras = externa.maquinas_terceros_compras()
    maquinarias_campo = externa.maquinarias_terceros_campo()
    colectivos = externa.colectivos_campo()
    lineas = externa.lineas_por_maquina(anio)

    alertas = alertas_cruce.detectar(
        maquinarias_campo, colectivos, maquinas_compras, maquinas_taller, lineas
    )
    return AlertasResponse(
        anio=anio,
        alertas=[vars(a) for a in alertas],
        maquinaria_campo=alertas_cruce.resumen_maquinaria_campo(
            maquinarias_campo, maquinas_compras, maquinas_taller
        ),
    )
