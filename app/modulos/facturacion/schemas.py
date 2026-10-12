"""Schemas Pydantic (request/response) del módulo Facturación.

Contrato de la E1 en docs/superpowers/plans/2026-10-11-facturacion-e1.md, 2.5.
"""
from typing import Optional

from pydantic import BaseModel


class TareaFacturacionOut(BaseModel):
    """Una tarea activa del sistema de campo con lo que tiene definido."""
    tarea_id: int
    nombre: str
    grupo_tarea: Optional[str]          # None = la tarea no tiene grupo en el campo
    unidad_sugerida: Optional[str]      # una clave de unidades.UNIDADES
    no_facturable: bool
    sin_definir: bool                   # sin Unidad sugerida y sin la marca


class DefinirTareaIn(BaseModel):
    """El estado completo de la tarea: los dos campos son obligatorios.

    {clave, false} es una Unidad sugerida, {null, true} es No facturable y
    {null, false} vuelve a Sin definir. Que no vayan las dos a la vez y que la
    unidad exista lo controla el servicio y no Pydantic, para que la regla sea
    la misma para la API y para el script de la primera carga."""
    unidad_sugerida: Optional[str]
    no_facturable: bool
