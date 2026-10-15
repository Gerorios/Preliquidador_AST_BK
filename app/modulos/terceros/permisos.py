"""Dependencias de autorización del módulo Liquidación Terceros sobre el núcleo
(app/core/permisos.py): cada endpoint exige Ver o Editar en una pantalla
(ADR-0020). El mapa endpoint → pantalla lo fija
tests/terceros/test_mapa_permisos.py."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_pantalla

MODULO = "terceros"

# Pantallas del módulo (ADR-0020). Las claves se guardan en la base y no cambian;
# el orden es el del editor de roles.
PANTALLAS = (
    Pantalla("inicio", "Inicio"),
    Pantalla("quincena", "Quincena"),
    Pantalla("tarifario", "Tarifario"),
    Pantalla("estaciones", "Estaciones"),
    Pantalla("verificaciones", "Verificaciones", editable=False),
    Pantalla("recibos", "Órdenes de facturación"),
)

# Dependencias con nombre, definidas una sola vez: FastAPI cachea por objeto.
# Con varias pantallas alcanza una; Editar incluye Ver; el admin pasa todo.

# Las quincenas son el selector de todas las pantallas: alcanza con ver una.
ver_alguna_pantalla = requiere_pantalla(MODULO, *(p.clave for p in PANTALLAS))

# Inicio: las liquidaciones de la quincena, y generarlas o calcularlas.
ver_inicio = requiere_pantalla(MODULO, "inicio")
editar_inicio = requiere_pantalla(MODULO, "inicio", nivel="editar")

# Totales y pendientes de la quincena: hoy no los usa ninguna pantalla.
ver_inicio_o_quincena = requiere_pantalla(MODULO, "inicio", "quincena")

# Quincena: la grilla, las cuotas de repuestos y mover un hecho de quincena.
# Los conjuntos de origen (viajes, combustible, etc.) también, aunque desde la
# etapa 8 no los usa ninguna pantalla.
ver_quincena = requiere_pantalla(MODULO, "quincena")
editar_quincena = requiere_pantalla(MODULO, "quincena", nivel="editar")

# Los bienes los leen Tarifario (Seguros) y Estaciones (carga a mano).
ver_bienes = requiere_pantalla(MODULO, "tarifario", "estaciones")

# Tarifario.
ver_tarifario = requiere_pantalla(MODULO, "tarifario")
editar_tarifario = requiere_pantalla(MODULO, "tarifario", nivel="editar")

# Estaciones.
ver_estaciones = requiere_pantalla(MODULO, "estaciones")
editar_estaciones = requiere_pantalla(MODULO, "estaciones", nivel="editar")

# Verificaciones y alertas de cruce (sólo Ver).
ver_verificaciones = requiere_pantalla(MODULO, "verificaciones")

# Órdenes de facturación (etapa 11): emitirlas, la factura de cada empresa, el
# pago, los ajustes, lo que llegó tarde y los saldos iniciales.
ver_recibos = requiere_pantalla(MODULO, "recibos")
editar_recibos = requiere_pantalla(MODULO, "recibos", nivel="editar")
