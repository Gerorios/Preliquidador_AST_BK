-- ─────────────────────────────────────────────────────────────────────────────
-- WS18 — Alerta "Posible duplicado" en la línea
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega `es_posible_duplicado` a preliquidacion_linea y la llena para todas
-- las quincenas existentes. Una línea es posible duplicado si otra de la misma
-- preliquidación es igual en planilla, fecha, legajo, empleado, tarea, cliente,
-- finca, tractor, unidades y tancadas, paga una cantidad mayor a 0 (unidades o
-- tancadas) y tiene horas distintas (jornal o máquina). Es excluyente con
-- `es_duplicado`: una línea duplicada no lleva además esta marca.
--
-- Por qué la cantidad > 0: sin ese filtro salen como posibles las tareas por
-- hora (misma cantidad nula, horas distintas), que casi siempre son trabajo
-- real; con el filtro quedan sólo los casos como el que originó la tarea.
--
-- La clave es la MISMA que arma el motor en Python (`clave_posible_duplicado`,
-- `paga_cantidad` y `detectar_posibles_duplicados` en
-- app/modulos/preliquidacion/services/motor_reglas.py). Si se cambia una, se
-- cambia la otra.
--
-- ⚠️  NO ES DIFERIBLE — mismo caso que WS16: el ORM declara la columna, así
-- que SQLAlchemy la incluye en todo SELECT/INSERT sobre preliquidacion_linea;
-- sin ella en la tabla real, hasta listar líneas falla con "Unknown column".
-- Aplicar primero en `testing`, después en producción, y en los dos ANTES de
-- reiniciar el backend con el código de esta rama.
--
-- El backfill (paso 2) es una semilla única: de acá en adelante la marca la
-- calcula el servicio en Python, al generar y en cada actualización de la
-- quincena que traiga altas o bajas. Una quincena que no se vuelva a
-- actualizar conserva lo que dejó este backfill.
--
-- Divergencias conocidas entre este SQL y el motor en Python (el SQL puede
-- marcar algo que Python no, o al revés; la próxima actualización con altas o
-- bajas lo corrige):
--   - La collation de la tabla (utf8mb4_0900_ai_ci) iguala acentos y
--     mayúsculas al agrupar; Python sólo iguala mayúsculas. "José" y "JOSE"
--     son el mismo grupo acá y dos grupos distintos en Python.
--   - TRIM saca sólo espacios; `.strip()` de Python saca también tabulaciones
--     y saltos de línea.
--
-- ⚠️  scripts/refrescar_testing.py recrea las tablas de testing con el
-- SHOW CREATE TABLE de producción: mientras producción no tenga esta columna,
-- correr ese script en testing la borra.
--
-- Reintento: si el ALTER del paso 1 ya se aplicó, correr sólo los UPDATE del
-- paso 2 (son idempotentes: el primero pone todo en 0 y el segundo vuelve a
-- marcar).
-- ─────────────────────────────────────────────────────────────────────────────

-- 1) Columna.
ALTER TABLE preliquidacion_linea
  ADD COLUMN es_posible_duplicado TINYINT(1) NOT NULL DEFAULT 0;

-- 2) Backfill. Misma clave que el motor sin las horas; cantidad > 0; horas distintas dentro
--    del grupo (MIN <> MAX del par de horas como texto equivale a "dos o más pares
--    distintos"); nunca sobre una duplicada.
UPDATE preliquidacion_linea SET es_posible_duplicado = 0;

UPDATE preliquidacion_linea l
JOIN (
  SELECT id, MIN(hs) OVER w AS hs_min, MAX(hs) OVER w AS hs_max
  FROM (
    SELECT id, preliquidacion_id,
           UPPER(TRIM(COALESCE(planilla, '')))        AS planilla_n,
           fecha_tarea,
           TRIM(COALESCE(legajo_campo, ''))           AS legajo_n,
           UPPER(TRIM(COALESCE(nombre_empleado, ''))) AS empleado_n,
           UPPER(TRIM(COALESCE(nombre_tarea, '')))    AS tarea_n,
           UPPER(TRIM(COALESCE(nombre_cliente, '')))  AS cliente_n,
           UPPER(TRIM(COALESCE(nombre_finca, '')))    AS finca_n,
           UPPER(TRIM(COALESCE(nombre_tractor, '')))  AS tractor_n,
           tancadas, unidades,
           CONCAT(COALESCE(CAST(hsjornal AS CHAR), 'None'), '|',
                  COALESCE(CAST(hsmaquina AS CHAR), 'None')) AS hs
    FROM preliquidacion_linea
    WHERE COALESCE(unidades, 0) > 0 OR COALESCE(tancadas, 0) > 0
  ) b
  WINDOW w AS (PARTITION BY preliquidacion_id, planilla_n, fecha_tarea, legajo_n, empleado_n,
                            tarea_n, cliente_n, finca_n, tractor_n, tancadas, unidades)
) g ON g.id = l.id
SET l.es_posible_duplicado = 1
WHERE g.hs_min <> g.hs_max
  AND COALESCE(l.es_duplicado, 0) = 0;

-- 3) Comprobación: conteo por quincena, y ninguna línea con las dos marcas.
SELECT p.quincena, COUNT(*) AS posibles
FROM preliquidacion_linea l JOIN preliquidacion p ON p.id = l.preliquidacion_id
WHERE l.es_posible_duplicado = 1 GROUP BY p.quincena ORDER BY p.quincena;
SELECT COUNT(*) FROM preliquidacion_linea WHERE es_posible_duplicado = 1 AND es_duplicado = 1;  -- 0

-- ─────────────────────────────────────────────────────────────────────────────
-- Rollback (sólo si hace falta volver atrás, y junto con el revert del código:
-- sin la columna, el código de esta rama falla con "Unknown column"):
--
-- ALTER TABLE preliquidacion_linea DROP COLUMN es_posible_duplicado;
-- ─────────────────────────────────────────────────────────────────────────────
