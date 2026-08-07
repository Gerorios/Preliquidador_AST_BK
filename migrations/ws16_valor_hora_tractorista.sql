-- ─────────────────────────────────────────────────────────────────────────────
-- WS16 — Valor hora tractorista del control Plantas vs Jornal
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega `valor_hora_tractorista` a la cabecera de quincena: el valor HORA
-- del tractorista que el liquidador carga en el control Plantas vs Jornal.
-- El jornal tractorista es este valor × 8, fijo para toda la tabla, y contra
-- él se compara lo que cobra la jornada pagada por planta (%Dif).
-- NULL = sin cargar (la comparación se muestra sin dato).
--
-- ⚠️  NO ES DIFERIBLE — mismo caso que WS7 (valor_hora_pulv): el ORM declara
-- la columna, así que SQLAlchemy la incluye en todo SELECT/INSERT sobre
-- preliquidacion; sin ella en la tabla real, hasta listar preliquidaciones
-- falla con "Unknown column". Aplicar ANTES o junto con el deploy de esta rama.
--
-- Nota histórica: una versión intermedia de esta migración creó la columna
-- como `valor_jornal_planta` (semántica "valor de la jornada"); el grilling
-- posterior la redefinió como valor hora. Si la base ya tiene esa columna,
-- aplicar en su lugar el rename equivalente:
--   ALTER TABLE preliquidacion
--     CHANGE valor_jornal_planta valor_hora_tractorista DECIMAL(12,2) NULL DEFAULT NULL;
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion
  ADD COLUMN valor_hora_tractorista DECIMAL(12, 2) NULL DEFAULT NULL;
