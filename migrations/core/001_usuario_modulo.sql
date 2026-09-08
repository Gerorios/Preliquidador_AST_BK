-- core/001 — Permisos por módulo (ADR-0013). NO DIFERIBLE: el código de esta
-- versión consulta usuario_modulo en cada request autenticado.
-- Aplicar UNA vez por base, junto con el deploy del PR 3 de la etapa 0.

CREATE TABLE IF NOT EXISTS usuario_modulo (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id  INT          NOT NULL,
    modulo      VARCHAR(30)  NOT NULL,   -- 'preliquidacion' | 'fletes' | ...
    rol         VARCHAR(20)  NOT NULL,   -- 'operador' | 'gerente'
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuario_modulo (usuario_id, modulo),
    CONSTRAINT fk_usuario_modulo_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Poblado desde los roles globales viejos (idempotente por la UNIQUE).
INSERT IGNORE INTO usuario_modulo (usuario_id, modulo, rol)
SELECT id, 'preliquidacion', 'operador' FROM usuarios WHERE rol = 'jefe';

INSERT IGNORE INTO usuario_modulo (usuario_id, modulo, rol)
SELECT id, 'preliquidacion', 'gerente' FROM usuarios WHERE rol = 'gerente';

-- El admin sigue global (sin filas). Los demás pasan a 'usuario'.
UPDATE usuarios SET rol = 'usuario' WHERE rol IN ('jefe', 'gerente');

-- Vuelta atrás (solo si hubiera que revertir el PR 3): el UPDATE reetiqueta
-- por lo que hay en usuario_modulo al momento de revertir, así que también
-- reetiqueta usuarios creados después del deploy (no solo los migrados acá
-- arriba). Un `usuario` sin fila en usuario_modulo (p. ej. si se revierte
-- antes de que se le haya asignado un módulo) queda con rol 'usuario', que
-- el código viejo (pre-PR 3, sin ADR-0013) no reconoce como rol válido.
--   UPDATE usuarios u JOIN usuario_modulo um ON um.usuario_id = u.id AND um.modulo = 'preliquidacion'
--      SET u.rol = CASE um.rol WHEN 'operador' THEN 'jefe' ELSE 'gerente' END WHERE u.rol = 'usuario';
--   DROP TABLE usuario_modulo;
