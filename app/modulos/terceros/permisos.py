"""Dependencias de autorización del módulo Liquidación Terceros sobre el núcleo."""
from app.core.permisos import requiere_modulo
MODULO = "terceros"
requiere_operativo = requiere_modulo(MODULO, "operador")
requiere_gerencial = requiere_modulo(MODULO, "gerente")
