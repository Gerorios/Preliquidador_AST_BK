-- ─────────────────────────────────────────────────────────────────────────────
-- Fix de trazabilidad: concepto_adicional pasa a ser un hecho autocontenido
-- Base: db_propia (sistema de preliquidación).
--
-- Hasta ahora concepto_adicional guardaba solo el importe final (cantidad *
-- precio) y descartaba los dos factores. Como concepto_liquidacion.precio es
-- mutable (se edita todo el tiempo, ver ADR-0002), no había forma de saber
-- después "a qué precio" o "por qué cantidad" se le pagó algo a una persona
-- sin arriesgarse a leer un precio ya desactualizado. Se agregan:
--
--   precio                  → precio unitario usado en el cálculo (snapshot)
--   cantidad                → cantidad de unidades reconocidas (snapshot)
--   concepto_liquidacion_id → FK a la regla exacta del maestro que originó
--                             el concepto (NULL para los conceptos manuales,
--                             que no tienen origen en el maestro)
--
-- ⚠️  NO ES DIFERIBLE — mismo caso que WS3/WS5: el modelo ORM ya intenta
-- escribir estas columnas en cada INSERT de ConceptoAdicional automático.
-- Verificado empíricamente: sin ellas, hasta un INSERT mínimo falla con
-- "no such column: precio". Aplicar ANTES o junto con el deploy de esta rama.
--
-- ⚠️  Irreversible. Hacer backup antes:
--     CREATE TABLE concepto_adicional_bkp_trazabilidad AS SELECT * FROM concepto_adicional;
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_adicional
  ADD COLUMN precio NUMERIC(12,4) NULL,
  ADD COLUMN cantidad NUMERIC(10,2) NULL,
  ADD COLUMN concepto_liquidacion_id INT NULL,
  ADD CONSTRAINT fk_concepto_adicional_origen
    FOREIGN KEY (concepto_liquidacion_id) REFERENCES concepto_liquidacion(id)
    ON DELETE SET NULL;
