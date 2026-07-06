-- ─────────────────────────────────────────────────────────────────────────────
-- WS3 — Completitud única: código y precio (ADR-0003)
-- Base: db_propia (sistema de preliquidación).
--
-- Colapsa alerta_sin_precio + alerta_sin_codigo en una sola columna
-- linea_incompleta.
--
-- ⚠️  A DIFERENCIA de las migraciones de WS1/WS2 (que solo borraban columnas
-- ya sin uso y podían diferirse), ESTA hay que aplicarla ANTES de deployar
-- el código de esta rama, o inmediatamente después sin dejar tráfico en el
-- medio. El modelo ORM ya escribe `linea_incompleta` en cada INSERT de
-- PreliquidacionLinea (generar/actualizar_quincena) — sin la columna en la
-- DB, esas operaciones fallan con "Unknown column 'linea_incompleta'".
-- Confirmado con un smoke test real (ver docs/adr/0003).
--
-- ⚠️  Irreversible. Hacer backup antes:
--     CREATE TABLE preliquidacion_linea_bkp_ws3 AS SELECT * FROM preliquidacion_linea;
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion_linea
  ADD COLUMN linea_incompleta TINYINT(1) NOT NULL DEFAULT 1;

-- Backfill: una línea está incompleta si antes tenía cualquiera de las dos
-- alertas viejas encendida.
UPDATE preliquidacion_linea
SET linea_incompleta = (alerta_sin_precio = 1 OR alerta_sin_codigo = 1);

ALTER TABLE preliquidacion_linea DROP COLUMN alerta_sin_precio;
ALTER TABLE preliquidacion_linea DROP COLUMN alerta_sin_codigo;
