"""Modelos SQLAlchemy del módulo Facturación.

Espejo de las migraciones de `migrations/facturacion/`. **La fuente de verdad
del esquema son ellas, no esto** (regla 9 de GUIA-MODULOS): acá se declara lo
mismo para que el ORM pueda leer y escribir, y para que el chequeo de tablas
faltantes del arranque cubra al módulo.

Hoy no hay tablas: la de la E1 se borró con `facturacion/002`, porque la Unidad
sugerida se lee del sistema de campo. La E2 suma acá las suyas.
"""
