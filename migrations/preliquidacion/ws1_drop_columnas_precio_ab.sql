-- ─────────────────────────────────────────────────────────────────────────────
-- WS1 — Retirar el modelo viejo de precios (ADR-0001)
-- Base: db_propia (sistema de preliquidación).
--
-- Deprecate-then-drop: el código de la rama ws1 YA NO referencia estas columnas.
-- Aplicar ESTE script DESPUÉS de deployar la rama, no antes.
--
-- ⚠️  DROP COLUMN es irreversible. Hacer backup de la tabla antes:
--     CREATE TABLE preliquidacion_linea_bkp_ws1 AS SELECT * FROM preliquidacion_linea;
--
-- Nota: MySQL no soporta "DROP COLUMN IF EXISTS". Si alguna columna ya no
-- existe en este entorno (p. ej. detalle_concepto), correr los ALTER de a uno
-- y saltear el que falle.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion_linea DROP COLUMN precio_b;
ALTER TABLE preliquidacion_linea DROP COLUMN precio_usado;

-- Columna huérfana del modelo viejo (ya no está en models.py; solo vive en la DB).
ALTER TABLE preliquidacion_linea DROP COLUMN detalle_concepto;

-- NO se dropea importe_base en WS1: el código todavía la escribe/lee (siempre 0).
-- Se elimina en un paso de limpieza posterior, junto con su remoción del código.
