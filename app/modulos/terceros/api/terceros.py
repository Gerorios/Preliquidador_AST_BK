"""Endpoints del módulo Liquidación Terceros. Molde: un solo endpoint de estado."""
from fastapi import APIRouter, Depends
from app.modulos.terceros.permisos import requiere_operativo

router = APIRouter(prefix="/api/terceros", tags=["Liquidación Terceros"], dependencies=[Depends(requiere_operativo)])


@router.get("/")
def estado():
    return {"modulo": "terceros", "estado": "en construcción"}
