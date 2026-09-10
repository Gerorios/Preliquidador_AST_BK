"""SQL crudo con text() y parámetros sobre las bases externas, solo lectura.

Dos orígenes (ver docs/modulos/terceros/plan-terceros.md):
  - Chinagro (get_db_externa): viajes y cargas de combustible de los colectivos.
  - La Falda (get_db_sueldos): repuestos y reparaciones de maquinaria de terceros.
Punto de partida: las consultas del Power Query, en docs/modulos/terceros/fuentes/."""
from sqlalchemy import text  # noqa: F401
