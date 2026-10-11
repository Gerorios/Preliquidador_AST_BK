"""Dependencias de autorización del módulo Liquidación Terceros sobre el núcleo."""
from app.core.modulos import Pantalla
from app.core.permisos import requiere_modulo
MODULO = "terceros"

# Pantallas del módulo (ADR-0020). Las claves se guardan en la base y no cambian;
# el orden es el del editor de roles.
PANTALLAS = (
    Pantalla("inicio", "Inicio"),
    Pantalla("quincena", "Quincena"),
    Pantalla("tarifario", "Tarifario"),
    Pantalla("estaciones", "Estaciones"),
    Pantalla("verificaciones", "Verificaciones", editable=False),
)
requiere_operativo = requiere_modulo(MODULO, "operador")
requiere_gerencial = requiere_modulo(MODULO, "gerente")
