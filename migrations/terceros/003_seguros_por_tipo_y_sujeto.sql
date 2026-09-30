-- terceros/003 — El seguro no siempre es de una máquina (etapa 6).
-- NO DIFERIBLE: el código de esta versión escribe `tipo_seguro` y `sujeto`.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- La 002 asumía que todo seguro es de una maquinaria. No lo es: de las tres
-- clases que llegan, una es del vehículo o la máquina (AUTOMOTOR) y las otras
-- dos son de una persona — el chofer en relación de dependencia y accidentes
-- personales. Con una sola columna `maquinaria` había que meter el nombre de
-- una persona en un campo que dice máquina, y el que leyera la tabla dentro de
-- un año no iba a entender qué está viendo.
--
-- Por eso:
--   tipo_seguro  de cuál de las tres clases es
--   sujeto       qué o a quién cubre: la máquina o la persona
--   referencia   cómo se lo identifica: la patente, o el CUIL del chofer
--
-- La 002 es de hoy y no llegó a producción, así que no hay datos que migrar:
-- lo cargado en `testing` es de prueba. Si hubiera filas, las de la 002 serían
-- todas AUTOMOTOR.

ALTER TABLE terceros_precio_seguro
    DROP INDEX uq_terceros_precio_seguro;

ALTER TABLE terceros_precio_seguro
    CHANGE COLUMN maquinaria sujeto VARCHAR(200) NOT NULL,
    ADD COLUMN tipo_seguro VARCHAR(30) NOT NULL DEFAULT 'AUTOMOTOR' AFTER tercero,
    ADD COLUMN referencia VARCHAR(60) NULL AFTER sujeto;

ALTER TABLE terceros_precio_seguro
    ADD UNIQUE KEY uq_terceros_precio_seguro (quincena, tercero, tipo_seguro, sujeto);

-- El DEFAULT existe sólo para que el ALTER pueda correr sobre filas ya
-- cargadas. De acá en más el tipo lo elige quien carga el seguro.
ALTER TABLE terceros_precio_seguro
    ALTER COLUMN tipo_seguro DROP DEFAULT;

-- ─── Vuelta atrás ───────────────────────────────────────────────────────────
--
-- ALTER TABLE terceros_precio_seguro DROP INDEX uq_terceros_precio_seguro;
-- ALTER TABLE terceros_precio_seguro
--     DROP COLUMN referencia,
--     DROP COLUMN tipo_seguro,
--     CHANGE COLUMN sujeto maquinaria VARCHAR(200) NOT NULL;
-- ALTER TABLE terceros_precio_seguro
--     ADD UNIQUE KEY uq_terceros_precio_seguro (quincena, tercero, maquinaria);
