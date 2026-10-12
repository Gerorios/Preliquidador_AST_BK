-- facturacion/001 — La Unidad sugerida o la marca No facturable de cada tarea del campo.
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy. Idempotente: si la tabla ya existe, no hace nada.
--
-- Una fila por cada tarea del sistema de campo que tiene algo definido, y sin
-- fila = Sin definir. Así una tarea nueva en el campo nace Sin definir sin que
-- nadie tenga que crearle nada, y volver a Sin definir es borrar la fila. Cada
-- fila tiene exactamente una de las dos cosas: una Unidad sugerida o la marca
-- No facturable. Lo controla el servicio y no la base, que no usa CHECK en el
-- resto del esquema.
--
-- La tarea se identifica por su id en el campo y no por el nombre: los partes
-- apuntan a la tarea por id, un renombre en el campo no pierde la Unidad
-- sugerida, y nada garantiza que el nombre sea único. Si el campo da de baja
-- una tarea, su fila no se borra: el Cruce puede necesitarla para partes viejos.
--
-- Vuelta atrás (sólo si se revierte la etapa entera, el código viejo convive con la tabla):
-- DROP TABLE IF EXISTS facturacion_tarea

CREATE TABLE IF NOT EXISTS facturacion_tarea (
    id               INT          AUTO_INCREMENT PRIMARY KEY,
    -- El id de la tarea en el sistema de campo.
    tarea_id         INT          NOT NULL,
    -- Una de las nueve claves de app/modulos/facturacion/unidades.py.
    unidad_sugerida  VARCHAR(20)  NULL,
    no_facturable    TINYINT(1)   NOT NULL DEFAULT 0,
    actualizado_en   DATETIME     NOT NULL,
    -- NULL = la cargó el script de la primera carga, no una persona.
    actualizado_por  INT          NULL,
    UNIQUE KEY uq_facturacion_tarea_tarea_id (tarea_id),
    CONSTRAINT fk_facturacion_tarea_usuario FOREIGN KEY (actualizado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
