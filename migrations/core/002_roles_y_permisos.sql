-- core/002 — Roles armables con permisos de ver o editar por pantalla (ADR-0020).
-- NO DIFERIBLE: el código de esta versión lee rol, rol_permiso y usuario_rol cada vez que
-- carga a la persona (login y cada pedido con sesión). Sin estas tablas no entra nadie.
-- Las tablas se crean si no existen y la carga inicial corre sólo si `rol` está vacía. La
-- carga inicial lee usuario_modulo, que core/003 borra: en una base que ya pasó por core/003
-- esta migración no se vuelve a correr (falla con "Table doesn't exist"). En una base nueva
-- sigue andando, porque ORDEN.txt corre 001, 002 y 003 en ese orden.

-- Los literales comparan con la collation de las tablas (si no, "Illegal mix of collations").
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rol (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    nombre     VARCHAR(60)  NOT NULL,
    creado_en  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rol_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rol_permiso (
    id        INT          AUTO_INCREMENT PRIMARY KEY,
    rol_id    INT          NOT NULL,
    modulo    VARCHAR(30)  NOT NULL,
    pantalla  VARCHAR(40)  NOT NULL,
    nivel     VARCHAR(10)  NOT NULL,
    UNIQUE KEY uq_rol_permiso (rol_id, modulo, pantalla),
    CONSTRAINT fk_rol_permiso_rol FOREIGN KEY (rol_id) REFERENCES rol(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS usuario_rol (
    id          INT       AUTO_INCREMENT PRIMARY KEY,
    usuario_id  INT       NOT NULL,
    rol_id      INT       NOT NULL,
    creado_en   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuario_rol (usuario_id, rol_id),
    CONSTRAINT fk_usuario_rol_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_usuario_rol_rol FOREIGN KEY (rol_id) REFERENCES rol(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET @sembrar = ((SELECT COUNT(*) FROM rol) = 0);

START TRANSACTION;

INSERT INTO rol (nombre)
SELECT t.nombre FROM (
              SELECT 'Preliquidador' AS nombre
    UNION ALL SELECT 'Gerente' AS nombre
    UNION ALL SELECT 'Liquidador de terceros' AS nombre
) t
WHERE @sembrar;

INSERT INTO rol_permiso (rol_id, modulo, pantalla, nivel)
SELECT r.id, p.modulo, p.pantalla, p.nivel FROM (
              SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'inicio' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'revision' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'verificacion' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'mantenimiento' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Preliquidador' AS rol, 'preliquidacion' AS modulo, 'conceptos' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Gerente' AS rol, 'preliquidacion' AS modulo, 'gerencial' AS pantalla, 'ver' AS nivel
    UNION ALL SELECT 'Gerente' AS rol, 'preliquidacion' AS modulo, 'conceptos' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'inicio' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'quincena' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'tarifario' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'estaciones' AS pantalla, 'editar' AS nivel
    UNION ALL SELECT 'Liquidador de terceros' AS rol, 'terceros' AS modulo, 'verificaciones' AS pantalla, 'ver' AS nivel
) p
JOIN rol r ON r.nombre = p.rol
WHERE @sembrar;

-- terceros/gerente no tiene equivalente (hoy no puede nada): no recibe rol (pregunta 1).
INSERT INTO usuario_rol (usuario_id, rol_id)
SELECT um.usuario_id, r.id
FROM usuario_modulo um
JOIN rol r ON r.nombre = CASE
    WHEN um.modulo = 'preliquidacion' AND um.rol = 'operador' THEN 'Preliquidador'
    WHEN um.modulo = 'preliquidacion' AND um.rol = 'gerente'  THEN 'Gerente'
    WHEN um.modulo = 'terceros'       AND um.rol = 'operador' THEN 'Liquidador de terceros'
END
WHERE @sembrar;

COMMIT;

-- Vuelta atrás: desde core/003 ya no hay código anterior al que volver sin tocar la base,
-- porque ese código lee usuario_modulo (ver la vuelta atrás de core/003). Estas tablas sólo
-- se borran si se abandona el esquema, en este orden y una sentencia por línea:
--   DROP TABLE usuario_rol;
--   DROP TABLE rol_permiso;
--   DROP TABLE rol;
