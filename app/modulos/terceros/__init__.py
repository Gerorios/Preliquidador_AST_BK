"""Módulo Liquidación Terceros.

Cubre los dos circuitos de liquidación a terceros, que comparten el mismo
sujeto que cobra y el mismo neto: Fletes (viajes de colectivos, combustible,
repuestos, seguros) y Horas de taller. Ver docs/modulos/terceros/.

Activo desde la etapa 2 (2026-09-14): el módulo dejó de ser un molde cuando
tuvo su primera pantalla real, que es la condición que fija CONTEXT.md en
"Módulo activo". Hoy sólo muestra lo que llega de los orígenes; no calcula ni
guarda nada — las tarifas y el neto empiezan en la etapa 4."""
from app.core.modulos import ModuloInfo
from app.modulos.terceros.api import terceros

routers = [terceros.router]
MODULO = ModuloInfo(
    clave="terceros", nombre="Liquidación Terceros",
    descripcion="Liquidación a terceros: fletes y horas de taller.",
    activo=True, routers=tuple(routers),
    etiquetas_rol={"operador": "Liquidador de terceros", "gerente": "Gerente"},
    panel_gerencial=False,
    modelos="app.modulos.terceros.models",
)
