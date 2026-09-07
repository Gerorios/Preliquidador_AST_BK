-- ─────────────────────────────────────────────────────────────────────────────
-- WS13 — Unidad base `jornal_tope1_mas_excedente`
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega el valor nuevo al ENUM de concepto_liquidacion.unidad_base:
-- igual a jornal_tope1 hasta las 10 hs (0 → 0; <5 → 0,5; 5..10 → 1) y por
-- encima de 10 hs paga hsjornal/10 redondeado a 2 decimales (11 hs → 1,1).
--
-- ⚠️  NO ES DIFERIBLE — sin este valor en el ENUM real, crear o editar un
-- concepto con la unidad nueva falla con "Data truncated for column
-- 'unidad_base'". Aplicar ANTES o exactamente junto con el deploy de esta
-- rama. Es un MODIFY que solo AGREGA un valor al final: no reescribe la
-- tabla ni toca los datos existentes.
--
-- (concepto_adicional.unidad_base es VARCHAR(30), no ENUM: el nombre nuevo
-- entra sin cambios — 26 caracteres.)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  MODIFY COLUMN unidad_base ENUM(
    'hsjornal',
    'hsmaquina',
    'tancadas',
    'unidades',
    'jornal_tope1',
    'jornal_tope1_mas_excedente',
    'fijo'
  ) NOT NULL;
