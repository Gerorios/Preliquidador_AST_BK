"""Módulo Fletes — molde (PR 4 etapa 0). Inactivo hasta que el módulo tenga
su primera pantalla real. Para desarrollar en local: activo=True."""
from app.core.modulos import ModuloInfo
from app.modulos.fletes.api import fletes

routers = [fletes.router]
MODULO = ModuloInfo(
    clave="fletes", nombre="Fletes",
    descripcion="Liquidación de fletes: viajes, tarifas y controles.",
    activo=False, routers=tuple(routers),
    etiquetas_rol={"operador": "Liquidador de fletes", "gerente": "Gerente"},
    panel_gerencial=False,
    modelos="app.modulos.fletes.models",
)
