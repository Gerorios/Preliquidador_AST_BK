"""Endpoints del módulo Fletes. Molde: un solo endpoint de estado."""
from fastapi import APIRouter, Depends
from app.modulos.fletes.permisos import requiere_operativo

router = APIRouter(prefix="/api/fletes", tags=["Fletes"], dependencies=[Depends(requiere_operativo)])


@router.get("/")
def estado():
    return {"modulo": "fletes", "estado": "en construcción"}
