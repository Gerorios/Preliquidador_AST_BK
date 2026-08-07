-- ─────────────────────────────────────────────────────────────────────────────
-- WS16 — Valor jornal del control Plantas vs Jornal
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega `valor_jornal_planta` a la cabecera de quincena: el valor de la
-- jornada de 8 hs que el liquidador carga en el control Plantas vs Jornal
-- para comparar lo pagado por planta contra pagar "a jornal"
-- (jornadas = hsmaquina/8 × este valor). Sin recargo, un valor por quincena.
-- NULL = sin cargar (la comparación se muestra sin dato).
--
-- ⚠️  NO ES DIFERIBLE — mismo caso que WS7 (valor_hora_pulv): el ORM declara
-- la columna, así que SQLAlchemy la incluye en todo SELECT/INSERT sobre
-- preliquidacion; sin ella en la tabla real, hasta listar preliquidaciones
-- falla con "Unknown column". Aplicar ANTES o junto con el deploy de esta rama.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE preliquidacion
  ADD COLUMN valor_jornal_planta DECIMAL(12, 2) NULL DEFAULT NULL;
