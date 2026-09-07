-- ─────────────────────────────────────────────────────────────────────────────
-- WS9 — Índices de latencia (optimización de lecturas)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega índices sobre preliquidacion_linea y concepto_adicional para las
-- consultas más frecuentes (listado/filtrado de líneas por preliquidación +
-- empresa/empleado/fecha, por CUIT, por tarea; y join de conceptos por línea
-- + usuario que los cargó). No cambian ningún resultado ni comportamiento
-- observable — son puramente de velocidad.
--
-- ✅  ES DIFERIBLE — a diferencia de WS7/WS8, estos índices NO son requeridos
-- por el ORM para que las consultas funcionen (el modelo sigue leyendo/
-- escribiendo igual sin ellos, solo más lento en tablas grandes). Se puede
-- aplicar en cualquier momento, incluso después del deploy del código, sin
-- romper nada mientras tanto.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX ix_linea_orden
  ON preliquidacion_linea (preliquidacion_id, empresa_asignada, nombre_empleado, fecha_tarea);

CREATE INDEX ix_linea_cuit
  ON preliquidacion_linea (preliquidacion_id, cuit);

CREATE INDEX ix_linea_tarea
  ON preliquidacion_linea (preliquidacion_id, nombre_tarea);

CREATE INDEX ix_concepto_linea_ingresado
  ON concepto_adicional (linea_id, ingresado_por);
