"""Módulo Liquidación Terceros — molde. Inactivo hasta que el módulo tenga
su primera pantalla real. Para desarrollar en local: activo=True.

Cubre los dos circuitos de liquidación a terceros, que comparten el mismo
sujeto que cobra y el mismo neto: Fletes (viajes de colectivos, combustible,
repuestos, seguros) y Horas de taller. Ver docs/modulos/terceros/."""
from app.core.modulos import ModuloInfo
from app.modulos.terceros.api import terceros

routers = [terceros.router]
MODULO = ModuloInfo(
    clave="terceros", nombre="Liquidación Terceros",
    descripcion="Liquidación a terceros: fletes y horas de taller.",
    activo=False, routers=tuple(routers),
    etiquetas_rol={"operador": "Liquidador de terceros", "gerente": "Gerente"},
    panel_gerencial=False,
    modelos="app.modulos.terceros.models",
)
