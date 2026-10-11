"""Dependencias de autorización del módulo Preliquidación sobre el núcleo
(app/core/permisos.py): cada endpoint exige Ver o Editar en una pantalla
(ADR-0020). El mapa endpoint → pantalla lo fija
tests/preliquidacion/test_mapa_permisos.py."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_pantalla

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

# Dependencias con nombre, definidas una sola vez: FastAPI cachea por objeto.
# Con varias pantallas alcanza una; Editar incluye Ver; el admin pasa todo.

# Inicio: generar o actualizar la quincena.
editar_inicio = requiere_pantalla(MODULO, "inicio", nivel="editar")

# El listado de quincenas es el selector de Inicio, Revisión, Verificación y
# Mantenimiento. Conceptos lo usa si la persona ve alguna de ellas; si no, usa
# `ver_quincenas_gerencial`. El front (Conceptos.jsx, `usaListado`) mira estas
# mismas cuatro pantallas: si cambian, cambian en los dos lados.
ver_quincenas = requiere_pantalla(MODULO, "inicio", "revision", "verificacion", "mantenimiento")

# Revisión.
ver_revision = requiere_pantalla(MODULO, "revision")
editar_revision = requiere_pantalla(MODULO, "revision", nivel="editar")

# Las líneas de la quincena las leen Revisión y Verificación.
ver_lineas = requiere_pantalla(MODULO, "revision", "verificacion")

# Verificación.
ver_verificacion = requiere_pantalla(MODULO, "verificacion")
editar_verificacion = requiere_pantalla(MODULO, "verificacion", nivel="editar")

# Mantenimiento (categorías de operarios de taller).
ver_mantenimiento = requiere_pantalla(MODULO, "mantenimiento")
editar_mantenimiento = requiere_pantalla(MODULO, "mantenimiento", nivel="editar")

# Conceptos (maestro de precios).
ver_conceptos = requiere_pantalla(MODULO, "conceptos")
editar_conceptos = requiere_pantalla(MODULO, "conceptos", nivel="editar")

# El combo de códigos de concepto lo usan Revisión (masiva y panel de la línea)
# y Conceptos.
ver_buscar_conceptos = requiere_pantalla(MODULO, "revision", "conceptos")

# Vista gerencial (sólo Ver).
ver_gerencial = requiere_pantalla(MODULO, "gerencial")

# Las quincenas generadas, para el selector de la Vista gerencial y de
# Conceptos cuando la persona no ve ninguna pantalla de `ver_quincenas`.
ver_quincenas_gerencial = requiere_pantalla(MODULO, "gerencial", "conceptos")
