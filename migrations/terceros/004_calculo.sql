-- terceros/004 — El cálculo del neto (etapa 7).
-- NO DIFERIBLE: el código de esta versión escribe estas columnas.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Hasta acá los hechos eran la foto de los orígenes y el tarifario era un
-- maestro de precios, sin nada que los uniera. Esto los une: cada hecho guarda
-- qué regla lo alcanzó, a qué precio y cuánto da.
--
-- Por qué se guarda y no se calcula al vuelo:
--   1. En la etapa 11 el recibo se congela al emitirse. No se puede congelar
--      algo que se recalcula cada vez que alguien abre la pantalla.
--   2. La grilla de la etapa 8 filtra y exporta sobre estas columnas. Con el
--      importe guardado es un SELECT; sin él, es recorrer cinco tarifarios por
--      cada fila.
-- Recalcular es explícito y es idempotente: se corre cuando cambia una tarifa.
--
-- `importe` es SIEMPRE POSITIVO, en las cinco tablas. El signo no vive en el
-- dato sino en el concepto — un viaje se paga y un repuesto se descuenta, y eso
-- no cambia nunca por fila. Guardarlo con signo invitaría a que alguna vez
-- entre un combustible en positivo y nadie lo note.
--
-- `estado_calculo` dice por qué una línea no tiene importe, y son razones
-- distintas que se resuelven con gente distinta:
--   CALCULADO       tiene tarifa y da un número
--   SIN_TERCERO     no se sabe de quién es el hecho — lo arregla el sistema de campo
--   SIN_TARIFA      nadie le pactó precio todavía — lo carga el liquidador
--   TARIFA_AMBIGUA  dos reglas igual de específicas lo alcanzan — lo desempata el liquidador
--   NO_COBRAR       alguien decidió no cobrarlo (repuestos)
--   NO_APROBADA     la hora de taller todavía no se aprobó (horas de reparación)
--   SIN_CANTIDAD    hay tarifa, pero la línea no trae la medida que esa tarifa
--                   cobra — una tarea pactada por cantidad sobre una planilla
--                   que sólo registró horas. Es un tarifario mal armado.
-- Ninguno de esos paga cero en silencio: los seis se listan aparte.

ALTER TABLE terceros_liquidacion
    ADD COLUMN calculada_en DATETIME NULL AFTER actualizada_en;

-- ─── Se pagan ───────────────────────────────────────────────────────────────

-- El tipo de viaje no es un dato del origen: lo resuelve la misma regla que
-- fija el precio. Por eso se copia acá al calcular.
ALTER TABLE terceros_viaje
    ADD COLUMN tarifa_id       INT            NULL AFTER motivo_efectiva,
    ADD COLUMN tipo_viaje      VARCHAR(10)    NULL AFTER tarifa_id,
    ADD COLUMN precio_aplicado DECIMAL(14,4)  NULL AFTER tipo_viaje,
    ADD COLUMN importe         DECIMAL(14,2)  NULL AFTER precio_aplicado,
    ADD COLUMN estado_calculo  VARCHAR(20)    NOT NULL DEFAULT 'SIN_TARIFA' AFTER importe;

-- `unidad_base` guarda cuál de las dos medidas se usó. La fila tiene las dos
-- cargadas (horas_maquina y unidades) y es la tarifa la que elige; sin esta
-- columna, mirando la línea no se sabe sobre qué se multiplicó.
ALTER TABLE terceros_hora_servicio
    ADD COLUMN tarifa_id       INT            NULL AFTER motivo_efectiva,
    ADD COLUMN unidad_base     VARCHAR(20)    NULL AFTER tarifa_id,
    ADD COLUMN cantidad_base   DECIMAL(12,2)  NULL AFTER unidad_base,
    ADD COLUMN precio_aplicado DECIMAL(14,4)  NULL AFTER cantidad_base,
    ADD COLUMN importe         DECIMAL(14,2)  NULL AFTER precio_aplicado,
    ADD COLUMN estado_calculo  VARCHAR(20)    NOT NULL DEFAULT 'SIN_TARIFA' AFTER importe;

-- ─── Se descuentan ──────────────────────────────────────────────────────────

ALTER TABLE terceros_carga_combustible
    ADD COLUMN tarifa_id       INT            NULL AFTER motivo_efectiva,
    ADD COLUMN precio_aplicado DECIMAL(14,4)  NULL AFTER tarifa_id,
    ADD COLUMN importe         DECIMAL(14,2)  NULL AFTER precio_aplicado,
    ADD COLUMN estado_calculo  VARCHAR(20)    NOT NULL DEFAULT 'SIN_TARIFA' AFTER importe;

ALTER TABLE terceros_hora_reparacion
    ADD COLUMN tarifa_id       INT            NULL AFTER motivo_efectiva,
    ADD COLUMN precio_aplicado DECIMAL(14,4)  NULL AFTER tarifa_id,
    ADD COLUMN importe         DECIMAL(14,2)  NULL AFTER precio_aplicado,
    ADD COLUMN estado_calculo  VARCHAR(20)    NOT NULL DEFAULT 'SIN_TARIFA' AFTER importe;

-- El repuesto no lleva tarifa: su precio viene calculado del sistema de compras
-- y el módulo no lo recalcula. Sólo se decide si se cobra o no.
ALTER TABLE terceros_repuesto
    ADD COLUMN importe        DECIMAL(14,2) NULL AFTER motivo_efectiva,
    ADD COLUMN estado_calculo VARCHAR(20)   NOT NULL DEFAULT 'CALCULADO' AFTER importe;

-- Para la grilla de la etapa 8, que filtra por "mostrame lo que quedó sin
-- precio". Sin esto es un full scan de la quincena por cada filtro.
CREATE INDEX ix_terceros_viaje_estado        ON terceros_viaje (liquidacion_id, estado_calculo);
CREATE INDEX ix_terceros_servicio_estado     ON terceros_hora_servicio (liquidacion_id, estado_calculo);
CREATE INDEX ix_terceros_combustible_estado  ON terceros_carga_combustible (liquidacion_id, estado_calculo);
CREATE INDEX ix_terceros_reparacion_estado   ON terceros_hora_reparacion (liquidacion_id, estado_calculo);
CREATE INDEX ix_terceros_repuesto_estado     ON terceros_repuesto (liquidacion_id, estado_calculo);
