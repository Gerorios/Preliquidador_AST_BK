-- ─────────────────────────────────────────────────────────────────────────────
-- WS7 — Valor hora de pulverización por quincena (ADR-0007)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega el parámetro que el liquidador carga a mano por quincena: el valor
-- de una hora de jornal de pulverización. Alimenta el control Tancadas vs
-- Jornal (valoriza "a jornal" el trabajo para compararlo contra el pago "a
-- tancada"). Sobre este valor se aplica un recargo fijo de pulverización
-- (×1,3) en código; ver ADR-0007 para el porqué de dejar el recargo fijo.
--
-- ⚠️  NO ES DIFERIBLE — el modelo ORM `Preliquidacion` ahora declara la
-- columna `valor_hora_pulv`. Aunque es nullable (sin default a nivel Python),
-- SQLAlchemy la referencia en los SELECT del ORM, así que sin la columna en
-- la tabla real cualquier lectura de Preliquidacion fallaría con
-- "Unknown column 'valor_hora_pulv'". Aplicar ANTES o exactamente junto con
-- el deploy de esta rama, no después.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion
  ADD COLUMN valor_hora_pulv DECIMAL(12,2) NULL;
