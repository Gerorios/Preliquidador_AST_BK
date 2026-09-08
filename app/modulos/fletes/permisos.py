"""Dependencias de autorización del módulo Fletes sobre el núcleo."""
from app.core.permisos import requiere_modulo
MODULO = "fletes"
requiere_operativo = requiere_modulo(MODULO, "operador")
requiere_gerencial = requiere_modulo(MODULO, "gerente")
