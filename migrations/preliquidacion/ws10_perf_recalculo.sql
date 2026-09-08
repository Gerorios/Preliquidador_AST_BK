-- ─────────────────────────────────────────────────────────────────────────────
-- WS10 — Sargabilidad del recálculo reactivo (optimización de lecturas)
-- Base: db_propia (sistema de preliquidación). Motor: MySQL 8.0.13+.
--
-- El recálculo reactivo del maestro (_lineas_por_match, recalcular_por_categoria,
-- operarios_mantenimiento en app/services/preliquidacion_service.py) filtra
-- preliquidacion_linea por func.upper(func.trim(nombre_tarea)) y por
-- func.upper(func.trim(cuit)). Sin un índice sobre esa EXPRESIÓN (no sobre la
-- columna cruda), MySQL no puede usar índice para esos WHERE — full scan de
-- preliquidacion_linea en cada recálculo.
--
-- Estos son índices FUNCIONALES (sobre expresión), soportados desde MySQL
-- 8.0.13. No se declaran en app/models/models.py: los tests corren sobre
-- SQLite, que no soporta esta sintaxis de índice funcional, y agregarlo al
-- modelo rompería la creación de tablas en los tests. Viven solo acá.
--
-- No cambian el código de las queries ni los datos guardados — puramente de
-- velocidad, sin impacto en el resultado.
--
-- ✅  ES DIFERIBLE — igual que WS9, el ORM sigue funcionando idéntico sin
-- estos índices (más lento en tablas grandes). Se puede aplicar en cualquier
-- momento, incluso después del deploy del código, sin romper nada mientras
-- tanto. Requiere MySQL 8.0.13+ (soporte de índices funcionales).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX ix_linea_tarea_norm
  ON preliquidacion_linea ((UPPER(TRIM(nombre_tarea))));

CREATE INDEX ix_linea_cuit_norm
  ON preliquidacion_linea ((UPPER(TRIM(cuit))));
