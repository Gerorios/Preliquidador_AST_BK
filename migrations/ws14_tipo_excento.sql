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
-- ANTES o exactamente junto con el deploy de esta rama. Es un MODIFY que
-- solo AGREGA un valor al final: no reescribe la tabla ni toca los datos
-- existentes.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  MODIFY COLUMN tipo ENUM(
    'REMUNERATIVO',
    'NO_REMUNERATIVO',
    'JORNAL',
    'BONO_BOLSON',
    'EXCENTO',
    'OTRO'
  ) NOT NULL DEFAULT 'OTRO';

ALTER TABLE concepto_adicional
  MODIFY COLUMN tipo ENUM(
    'REMUNERATIVO',
    'NO_REMUNERATIVO',
    'JORNAL',
    'BONO_BOLSON',
    'EXCENTO',
    'OTRO'
  ) DEFAULT 'OTRO';
