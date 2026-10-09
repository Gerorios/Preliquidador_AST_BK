"""Dependencias de autorización del módulo Preliquidación sobre el núcleo
(app/core/permisos.py). Quién pasa: ver CONTEXT-preliquidacion.md "Roles en Preliquidación" y ADR-0013."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_modulo

MODULO = "preliquidacion"

# Pantallas del módulo (ADR-0020). Las claves se guardan en la base y no cambian;
# el orden es el del editor de roles.
PANTALLAS = (
    Pantalla("inicio", "Inicio"),
    # Revisión no tiene entrada de menú: se abre desde el Inicio del módulo.
    Pantalla("revision", "Revisión", requiere=("inicio",)),
    Pantalla("verificacion", "Verificación"),
    Pantalla("mantenimiento", "Mantenimiento"),
    Pantalla("conceptos", "Conceptos"),
    Pantalla("gerencial", "Vista gerencial", editable=False),
)

# Opera la preliquidación completa: admin y operador (liquidador).
requiere_operativo = requiere_modulo(MODULO, "operador")

# El gerente opera el maestro de Conceptos completo porque es quien muchas
# veces decide un cambio de precios; el resto de lo operativo le sigue vedado.
requiere_conceptos = requiere_modulo(MODULO, "operador", "gerente")

# Panel gerencial: gerente y admin. El operador NO (decisión 2026-09-08).
requiere_gerencial = requiere_modulo(MODULO, "gerente")
