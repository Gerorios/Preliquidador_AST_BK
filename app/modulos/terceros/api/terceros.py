"""Endpoints del módulo Liquidación Terceros.

Etapa 2 del plan: los cuatro conjuntos de una quincena, de **solo lectura**.
No hay POST ni PATCH todavía y no se escribe en ninguna base: el módulo no
tiene tablas propias hasta la etapa 4. Cada pedido va a los orígenes y
devuelve lo que hay.

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
    CargaCombustibleResponse,
    HorasTallerResponse,
    QuincenaResponse,
    RepuestoResponse,
    ViajeResponse,
)
from app.modulos.terceros.services import quincenas
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


@router.get("/horas-taller", response_model=HorasTallerResponse)
def listar_horas_taller(
    quincena: date = Depends(quincena_param),
    servicio: ConsultaTallerService = Depends(get_consulta_taller),
):
    """Las horas cobrables de la quincena, más el recuento por estado.

    `horas` trae las aprobadas y las pendientes; las rechazadas no están porque
    no se cobran nunca. `estados` las cuenta a las tres: sirve para reclamarle
    al taller **antes** de liquidar, porque una hora que quede pendiente cuando
    se emita el recibo es plata que no se factura en esta quincena.

    Las dos cosas vienen juntas porque salen de la misma lectura del Sheet, que
    tarda unos seis segundos: pedirlas por separado lo bajaba dos veces.
    """
    try:
        return HorasTallerResponse(
            horas=servicio.horas_quincena(quincena),
            estados=servicio.estados_quincena(quincena),
        )
    except FALLAS_DE_ORIGEN as e:
        raise HTTPException(status_code=502, detail=_mensaje_origen(e))
