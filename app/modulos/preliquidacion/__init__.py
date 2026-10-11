"""
Módulo Preliquidación (de sueldos): el primer módulo del sistema (ADR-0013).

Expone `routers` para que app/main.py lo registre. El orden importa solo para
la documentación OpenAPI; se conserva el orden histórico.
"""
from app.core.modulos import ModuloInfo
from app.modulos.preliquidacion.api import preliquidacion, precios, export, gerencial
from app.modulos.preliquidacion.permisos import PANTALLAS

routers = [preliquidacion.router, precios.router, export.router, gerencial.router]

MODULO = ModuloInfo(
    clave="preliquidacion",
    nombre="Preliquidación",
    descripcion="Sueldos por quincena: generar, revisar, verificar y exportar.",
    activo=True,
    routers=tuple(routers),
    panel_gerencial=True,
    modelos="app.modulos.preliquidacion.models",
    pantallas=PANTALLAS,
)
