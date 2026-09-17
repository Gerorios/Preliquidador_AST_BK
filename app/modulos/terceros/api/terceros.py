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
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_externa, get_db_sueldos
from app.modulos.terceros.permisos import requiere_operativo
from app.modulos.terceros.schemas import (
    AlertasResponse,
    CargaCombustibleResponse,
    HoraServicioResponse,
    HorasReparacionResponse,
    QuincenaResponse,
    RepuestoResponse,
    ViajeResponse,
)
from app.modulos.terceros.services import alertas_cruce, quincenas
from app.modulos.terceros.services.consulta_externa import ConsultaExternaService
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


@router.get("/")
def estado():
    return {"modulo": "terceros", "estado": "en construcción"}


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
