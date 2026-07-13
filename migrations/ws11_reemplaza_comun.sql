-- ─────────────────────────────────────────────────────────────────────────────
-- WS11 — Reemplaza común (concepto específico descarta los comunes)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega el tilde opcional `reemplaza_comun` a concepto_liquidacion. Solo
-- tiene sentido en un concepto ESPECÍFICO (cliente_nombre NOT NULL): si una
-- línea matchea un específico con reemplaza_comun=1, se descartan los
-- conceptos COMUNES de esa tarea para esa línea (paga solo el/los
-- específico/s). Default 0: comportamiento actual intacto (comunes y
-- específicos siempre suman).
--
-- ⚠️  NO ES DIFERIBLE — mismo caso que WS5/WS8: el modelo ORM
-- `ConceptoLiquidacion` declara `reemplaza_comun` con default a nivel Python,
-- así que SQLAlchemy lo incluye en TODO INSERT/SELECT sobre
-- concepto_liquidacion, no solo cuando se usa el tilde. Sin esta columna en
-- la tabla real, hasta crear_concepto (el POST normal, sin tocar el tilde)
-- fallaría con "Unknown column 'reemplaza_comun' in 'field list'".
-- Aplicar ANTES o exactamente junto con el deploy de esta rama, no después.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  ADD COLUMN reemplaza_comun TINYINT(1) NOT NULL DEFAULT 0;
