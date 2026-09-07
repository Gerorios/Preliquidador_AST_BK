"""
Módulo Preliquidación (de sueldos): el primer módulo del sistema (ADR-0013).

Expone `routers` para que app/main.py lo registre. El orden importa solo para
la documentación OpenAPI; se conserva el orden histórico.
"""
from app.modulos.preliquidacion.api import preliquidacion, precios, export, gerencial

routers = [preliquidacion.router, precios.router, export.router, gerencial.router]
