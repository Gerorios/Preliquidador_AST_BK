"""Roles de prueba compartidos por la suite (ADR-0020).

`SEMILLA` son los permisos de los tres roles que crea la migración
`migrations/core/002_roles_y_permisos.sql`, que copian el acceso del esquema
anterior por módulo. `tests/core/test_migracion_roles.py` verifica que el SQL
cargue exactamente estas filas; los tests de BK2 arman a las personas con estos
mismos roles, con `usuario_con`.
"""
from types import SimpleNamespace

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

# Lo que migraciones posteriores le suman a esos roles. `SEMILLA` sigue siendo
# exactamente lo que carga core/002 (lo verifica test_migracion_roles.py); con
# esto, el rol de prueba es el que queda en una base con todas las migraciones.
AGREGADOS = (
    # terceros/013: la pantalla Órdenes de facturación, de la etapa 11.
    ("Liquidador de terceros", "terceros", "recibos", "editar"),
)


def rol_de_semilla(nombre: str) -> SimpleNamespace:
    """El rol `nombre` de `SEMILLA`, con lo que le suman `AGREGADOS`, como objeto
    simulado con `nombre` y `permisos`."""
    permisos = [
        SimpleNamespace(modulo=m, pantalla=p, nivel=n)
        for r, m, p, n in SEMILLA + AGREGADOS
        if r == nombre
    ]
    if not permisos:
        raise ValueError(f"{nombre!r} no es un rol de la semilla")
    return SimpleNamespace(nombre=nombre, permisos=permisos)


def usuario_con(*roles: str, rol: str = "usuario") -> SimpleNamespace:
    """Persona simulada con los roles de la semilla nombrados en `roles`.
    `rol` es la marca global ('admin' pasa todo). Sin roles, no ve nada."""
    return SimpleNamespace(
        id=1, nombre="Test", email="t@t.com", rol=rol, activo=True,
        roles=[rol_de_semilla(r) for r in roles],
    )
