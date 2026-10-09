"""Roles de prueba compartidos por la suite (ADR-0020).

`SEMILLA` son los permisos de los tres roles que crea la migración
`migrations/core/002_roles_y_permisos.sql`, que copian el acceso del esquema
anterior por módulo. `tests/core/test_migracion_roles.py` verifica que el SQL
cargue exactamente estas filas; los tests de BK2 arman a las personas con estos
mismos roles.
"""

# (rol, módulo, pantalla, nivel), en el orden de la migración.
SEMILLA = (
    ("Preliquidador", "preliquidacion", "inicio", "editar"),
    ("Preliquidador", "preliquidacion", "revision", "editar"),
    ("Preliquidador", "preliquidacion", "verificacion", "editar"),
    ("Preliquidador", "preliquidacion", "mantenimiento", "editar"),
    ("Preliquidador", "preliquidacion", "conceptos", "editar"),
    ("Gerente", "preliquidacion", "gerencial", "ver"),
    ("Gerente", "preliquidacion", "conceptos", "editar"),
    ("Liquidador de terceros", "terceros", "inicio", "editar"),
    ("Liquidador de terceros", "terceros", "quincena", "editar"),
    ("Liquidador de terceros", "terceros", "tarifario", "editar"),
    ("Liquidador de terceros", "terceros", "estaciones", "editar"),
    ("Liquidador de terceros", "terceros", "verificaciones", "ver"),
)
