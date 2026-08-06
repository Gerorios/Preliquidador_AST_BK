-- ─────────────────────────────────────────────────────────────────────────────
-- WS14 — Tipo de concepto `EXCENTO`
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega el valor nuevo al ENUM de concepto_liquidacion.tipo y
-- concepto_adicional.tipo. EXCENTO es una etiqueta pura (grafía deliberada,
-- no "exento"): marca importes exentos de aportes/cargas sociales. Ningún
-- cálculo del sistema la distingue; la aprovechan el contador y los reportes.
--
-- ⚠️  NO ES DIFERIBLE — sin este valor en el ENUM real, guardar un concepto
-- con tipo EXCENTO falla con "Data truncated for column 'tipo'". Aplicar
-- ANTES o exactamente junto con el deploy de esta rama. EXCENTO va AL FINAL
-- de la lista del ENUM a propósito: agregar al final es un cambio instantáneo
-- de metadata (sin rebuild de tabla ni lock); insertarlo en el medio obligaría
-- a MySQL a reconstruir la tabla. El orden del ENUM es invisible para la app.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  MODIFY COLUMN tipo ENUM(
    'REMUNERATIVO',
    'NO_REMUNERATIVO',
    'JORNAL',
    'BONO_BOLSON',
    'OTRO',
    'EXCENTO'
  ) NOT NULL DEFAULT 'OTRO';

ALTER TABLE concepto_adicional
  MODIFY COLUMN tipo ENUM(
    'REMUNERATIVO',
    'NO_REMUNERATIVO',
    'JORNAL',
    'BONO_BOLSON',
    'OTRO',
    'EXCENTO'
  ) DEFAULT 'OTRO';
