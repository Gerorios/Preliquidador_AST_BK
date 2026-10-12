"""Dependencias de autorización del módulo Facturación sobre el núcleo
(app/core/permisos.py): cada endpoint exige Ver o Editar en una pantalla
(ADR-0020). El mapa endpoint → pantalla lo fija
tests/facturacion/test_mapa_permisos.py."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_pantalla

MODULO = "facturacion"

# Pantallas del módulo (ADR-0020). Las claves se guardan en la base y no cambian;
# el orden es el del editor de roles. Las cinco se declaran desde la E1 para que
# las claves queden fijas, aunque ninguna tenga endpoints todavía: quien sólo
# tenga pantallas sin construir no ve nada, y no se rompe (plan de la E1, D2).
# Ninguna requiere otra.
#
# La clave `unidad` (Unidad de medida por defecto) se retiró el 2026-10-12: la
# Unidad sugerida se lee del sistema de campo
# (docs/superpowers/plans/2026-10-12-unidad-desde-campo.md). No se reutiliza
# nunca: un rol con permisos viejos ganaría la pantalla nueva.
PANTALLAS = (
    Pantalla("pendientes", "Pendientes"),
    Pantalla("cruce", "Cruce", editable=False),
    Pantalla("comprobantes", "Comprobantes"),
    Pantalla("equivalencias", "Equivalencias"),
    Pantalla("panel", "Panel", editable=False),
)

# Dependencias con nombre, definidas una sola vez: FastAPI cachea por objeto.
# Editar incluye Ver; el admin pasa todo. Cada pantalla suma las suyas en su
# etapa.

# Comprobantes (E2): el listado, el detalle y las lecturas del campo y de
# sueldos que usa el alta (clientes, fincas, empresas y tareas) piden Ver;
# alta, edición y borrado, Editar. Las lecturas del campo van con Comprobantes
# porque hoy es la única pantalla que las usa.
ver_comprobantes = requiere_pantalla(MODULO, "comprobantes")
editar_comprobantes = requiere_pantalla(MODULO, "comprobantes", nivel="editar")
