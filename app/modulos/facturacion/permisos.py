"""Dependencias de autorización del módulo Facturación sobre el núcleo
(app/core/permisos.py): cada endpoint exige Ver o Editar en una pantalla
(ADR-0020). El mapa endpoint → pantalla lo fija
tests/facturacion/test_mapa_permisos.py."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_pantalla

MODULO = "facturacion"

# Pantallas del módulo (ADR-0020). Las claves se guardan en la base y no cambian;
# el orden es el del editor de roles. Las seis se declaran desde la E1 para que
# las claves queden fijas, aunque sólo `unidad` tenga endpoints todavía: quien
# sólo tenga pantallas sin construir no ve nada, y no se rompe (plan de la E1,
# D2). Ninguna requiere otra.
PANTALLAS = (
    Pantalla("pendientes", "Pendientes"),
    Pantalla("cruce", "Cruce", editable=False),
    Pantalla("comprobantes", "Comprobantes"),
    Pantalla("unidad", "Unidad de medida por defecto"),
    Pantalla("equivalencias", "Equivalencias"),
    Pantalla("panel", "Panel", editable=False),
)

# Dependencias con nombre, definidas una sola vez: FastAPI cachea por objeto.
# Editar incluye Ver; el admin pasa todo. Las otras cinco pantallas suman las
# suyas en su etapa.

# Unidad de medida por defecto: ver la Unidad sugerida y la marca No facturable
# de cada tarea, y definirlas.
ver_unidad = requiere_pantalla(MODULO, "unidad")
editar_unidad = requiere_pantalla(MODULO, "unidad", nivel="editar")
