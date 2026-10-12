"""Módulo Facturación.

Registra cada Comprobante emitido a un cliente, lo traduce a tareas del
sistema de campo y lo cruza contra lo que efectivamente se trabajó, para saber
qué falta facturar y dónde se facturó de más o de menos. Cubre las tareas
agrícolas; la cosecha queda fuera. Ver docs/modulos/facturacion/.

Activo desde la E1 (2026-10-11), con sus cinco pantallas declaradas para el
editor de roles y ninguna construida todavía: no monta rutas hasta la E2. La
pantalla de la E1 se retiró el 2026-10-12."""
from app.core.modulos import ModuloInfo
from app.modulos.facturacion.permisos import PANTALLAS

MODULO = ModuloInfo(
    clave="facturacion", nombre="Facturación",
    descripcion="Lo que se factura a los clientes por las tareas agrícolas, "
                "cruzado contra lo trabajado en el campo.",
    activo=True, routers=(),
    panel_gerencial=False,
    modelos="app.modulos.facturacion.models",
    pantallas=PANTALLAS,
)
