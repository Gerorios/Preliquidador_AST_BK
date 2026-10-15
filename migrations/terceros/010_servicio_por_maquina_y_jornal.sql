-- terceros/010 — La tarifa de horas de servicio por máquina, y el jornal.
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Dos cambios que pidió el usuario (2026-10-05):
--
--   1. **La máquina es una dimensión de la tarifa.** El precio de una hora de
--      servicio varía según la máquina, y hasta acá la regla sólo sabía de
--      tercero, cliente, finca y tarea.
--   2. **Se puede pagar por jornal**: las horas de jornal que se cargan en el
--      sistema de campo, divididas por 10. Hasta acá el módulo no las traía,
--      porque la regla era que el jornal no se pagaba nunca.
--
-- En producción no hay ninguna tarifa de servicio ni ninguna quincena
-- generada: no hay nada que convertir.

ALTER TABLE terceros_hora_servicio
    ADD COLUMN horas_jornal DECIMAL(10, 2) NULL AFTER horas_maquina;

-- '' y no NULL, como el resto de las dimensiones: en MySQL un UNIQUE deja
-- pasar varias filas con NULL, y dos reglas iguales son el empate que el
-- módulo no sabe resolver.
--
-- Tarea y máquina entran al índice por sus primeros 150 caracteres: con las
-- seis dimensiones enteras la clave pasa los 3.072 bytes que admite InnoDB en
-- utf8mb4. Alcanza de sobra: en el sistema de campo el nombre más largo es de
-- 73 caracteres en tareas y de 56 en máquinas (medido el 2026-10-05).
ALTER TABLE terceros_tarifa_servicio
    ADD COLUMN maquinaria VARCHAR(200) NOT NULL DEFAULT '' AFTER tarea,
    DROP INDEX uq_terceros_tarifa_servicio,
    ADD UNIQUE KEY uq_terceros_tarifa_servicio
        (quincena, tercero, cliente, finca, tarea(150), maquinaria(150));
