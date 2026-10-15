-- terceros/012 — Las tarifas y los seguros atados al id de la máquina.
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Al reorganizar el maestro de maquinaria del sistema de campo cambiaron los
-- nombres de las máquinas, y las tarifas de servicio y los seguros dejaron de
-- encontrar la suya: estaban atados al nombre (2026-10-07). Con el id, al
-- actualizar una quincena el módulo les pone el nombre nuevo solo.
--
-- Nulo donde todavía no se sabe: lo carga el módulo al actualizar o al guardar.

-- El id de la máquina en el sistema de campo.
ALTER TABLE terceros_hora_servicio
    ADD COLUMN id_maquinaria INT NULL AFTER maquinaria;

ALTER TABLE terceros_tarifa_servicio
    ADD COLUMN id_maquinaria INT NULL AFTER maquinaria;

-- El bien del padrón que cubre la póliza: 'colectivo', 'maquinaria' o 'chofer',
-- y su id en el sistema de campo.
ALTER TABLE terceros_precio_seguro
    ADD COLUMN origen VARCHAR(20) NULL AFTER sujeto,
    ADD COLUMN id_origen INT NULL AFTER origen;
