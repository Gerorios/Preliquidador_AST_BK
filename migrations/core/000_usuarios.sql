-- Esquema base generado con scripts/exportar_esquema.py desde la base real
-- (preliquidacion) el 2026-09-08. Es el punto de partida para una base nueva: correr este
-- archivo y después las migraciones siguientes de la carpeta en orden.
-- NO editar a mano: regenerar con el script.

-- usuarios
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `rol` varchar(20) DEFAULT NULL,
  `contratos` varchar(50) DEFAULT NULL,
  `activo` tinyint(1) DEFAULT NULL,
  `creado_en` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

