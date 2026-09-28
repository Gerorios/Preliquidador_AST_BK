-- terceros/005 — La observación de la carga de combustible (etapa 9).
-- NO DIFERIBLE: el código de esta versión la lee y la guarda.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- El sistema de campo tiene un campo libre en cada carga y el módulo no lo
-- traía. Resulta que es lo que explica la mitad de los vales repetidos:
--
--   vale 60300, 25/08, CORNEJO, MATIAS
--     150 L  "En la misma orden se le dio 1 tacho de aceite de motor por 20 lts"
--       1 L  (sin observación)
--
-- Sin la observación, esa carga de 1 litro parece un error de tipeo y alguien
-- va a ir a borrarla. Con la observación se entiende sola, sin salir de la
-- pantalla ni preguntarle a quien la cargó.
--
-- En agosto, 359 de 2.230 cargas tienen algo escrito acá.

ALTER TABLE terceros_carga_combustible
    ADD COLUMN observacion TEXT NULL AFTER usuario_carga;
