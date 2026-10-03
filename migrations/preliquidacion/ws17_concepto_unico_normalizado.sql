-- ─────────────────────────────────────────────────────────────────────────────
-- WS17 — Un Concepto no se repite (ADR-0018)
-- Base: db_propia (sistema de preliquidación).
--
-- Reemplaza el índice único `uq_concepto_unif` de concepto_liquidacion por uno
-- funcional sobre la clave normalizada: quincena + tarea + cliente + finca +
-- supervisor + código + categoría, con TRIM, sin distinguir mayúsculas y con
-- vacío igual a NULL. El precio no participa: con otro precio sigue siendo la
-- misma regla, y para cambiarlo se edita.
--
-- Por qué: el índice viejo, sobre columnas crudas, no frenaba nada. Cada regla
-- tiene cliente o supervisor en NULL (ADR-0011), y para la base dos NULL nunca
-- son iguales, así que dos reglas idénticas entraban sin error y el motor las
-- sumaba (pagaba dos veces).
--
-- La expresión del índice es la MISMA que declara el modelo ORM
-- (`ConceptoLiquidacion.__table_args__` en app/modulos/preliquidacion/models.py).
-- Si se cambia una, se cambia la otra.
--
-- Se aplica en el mismo deploy que el código. El orden entre los dos no rompe
-- nada: el código no falla contra el índice viejo (sólo traduce a 409 el
-- rechazo de `uq_concepto_unif`, que con el índice viejo nunca llega), pero
-- hasta aplicar esta migración la base no impide los repetidos.
--
-- ⚠️  La base NO acepta el cambio si quedan Conceptos repetidos: el ALTER falla
-- con "Duplicate entry" y el índice viejo queda como estaba (el ALTER es
-- atómico). Por eso primero se corre la verificación previa y tiene que dar 0
-- filas. Si devuelve algo, NO seguir: el liquidador unifica esas reglas desde
-- la pantalla de Conceptos (no por SQL crudo) y se vuelve a verificar.
--
-- ⚠️  scripts/refrescar_testing.py recrea las tablas de testing con el
-- SHOW CREATE TABLE de producción: mientras producción no tenga este índice,
-- correr ese script en testing pisa el índice nuevo con el viejo.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1) Verificación previa: tiene que dar 0 filas.
SELECT
  quincena,
  UPPER(TRIM(tarea_nombre))                   AS tarea_n,
  COALESCE(UPPER(TRIM(cliente_nombre)), '')    AS cliente_n,
  COALESCE(UPPER(TRIM(finca_nombre)), '')      AS finca_n,
  COALESCE(UPPER(TRIM(supervisor_nombre)), '') AS supervisor_n,
  COALESCE(codigo, -1)                         AS codigo_n,
  COALESCE(categoria, 0)                       AS categoria_n,
  COUNT(*)                                     AS repetidas,
  GROUP_CONCAT(id ORDER BY id)                 AS ids
FROM concepto_liquidacion
GROUP BY quincena, tarea_n, cliente_n, finca_n, supervisor_n, codigo_n, categoria_n
HAVING COUNT(*) > 1;

-- 2) Backup.
CREATE TABLE concepto_liquidacion_bkp_ws17 AS SELECT * FROM concepto_liquidacion;

-- 3) Cambio del índice: un solo ALTER, atómico en MySQL 8 (si falla, no
--    queda la tabla sin índice).
ALTER TABLE concepto_liquidacion
  DROP INDEX uq_concepto_unif,
  ADD UNIQUE INDEX uq_concepto_unif (
    quincena,
    (UPPER(TRIM(tarea_nombre))),
    (COALESCE(UPPER(TRIM(cliente_nombre)), '')),
    (COALESCE(UPPER(TRIM(finca_nombre)), '')),
    (COALESCE(UPPER(TRIM(supervisor_nombre)), '')),
    (COALESCE(codigo, -1)),
    (COALESCE(categoria, 0))
  );

-- 4) Comprobación: uq_concepto_unif con Non_unique = 0, siete partes, y las
--    funcionales con la expresión en la columna Expression.
SHOW INDEX FROM concepto_liquidacion WHERE Key_name = 'uq_concepto_unif';

-- ─────────────────────────────────────────────────────────────────────────────
-- Rollback (sólo si hace falta volver atrás): vuelve al índice viejo sobre
-- columnas crudas, el que dejó WS15.
--
-- ALTER TABLE concepto_liquidacion
--   DROP INDEX uq_concepto_unif,
--   ADD UNIQUE INDEX uq_concepto_unif (
--     quincena, tarea_nombre, cliente_nombre, finca_nombre, codigo, categoria,
--     supervisor_nombre
--   );
--
-- Al cerrar (deploy verificado, sin rollback), borrar el backup:
--
-- DROP TABLE concepto_liquidacion_bkp_ws17;
-- ─────────────────────────────────────────────────────────────────────────────
