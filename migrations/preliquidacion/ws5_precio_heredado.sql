-- ─────────────────────────────────────────────────────────────────────────────
-- WS5 — Copiar autoaplica y precio heredado (ADR-0004)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega la marca "heredado" a concepto_liquidacion: un concepto copiado de
-- otra quincena nace con heredado=1 (paga normal, pero se resalta/filtra en
-- el frontend hasta que el liquidador confirme el precio, lo que limpia la
-- marca a 0).
--
-- ⚠️  NO ES DIFERIBLE (a diferencia de WS1/WS2) — mismo caso que WS3: el
-- modelo ORM tiene `heredado` con default a nivel Python, así que
-- SQLAlchemy lo incluye en TODO INSERT de ConceptoLiquidacion, no solo al
-- copiar. Verificado empíricamente: sin esta columna en la tabla real,
-- hasta crear_concepto (el POST normal de un concepto, sin copiar nada)
-- falla con "Unknown column 'heredado' in 'field list'".
-- Aplicar ANTES o exactamente junto con el deploy de esta rama, no después.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  ADD COLUMN heredado TINYINT(1) NOT NULL DEFAULT 0;
