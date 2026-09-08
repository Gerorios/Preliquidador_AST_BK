-- ─────────────────────────────────────────────────────────────────────────────
-- WS2 — Modelo reactivo + eliminación del estado "revisado" (ADR-0002)
-- Base: db_propia (sistema de preliquidación).
--
-- El código de la rama ws2 YA NO referencia esta columna. Aplicar ESTE
-- script DESPUÉS de deployar la rama, no antes.
--
-- ⚠️  DROP COLUMN es irreversible. Hacer backup de la tabla antes:
--     CREATE TABLE preliquidacion_linea_bkp_ws2 AS SELECT * FROM preliquidacion_linea;
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion_linea DROP COLUMN revisado;
