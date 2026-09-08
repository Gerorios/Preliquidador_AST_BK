-- Esquema base generado con scripts/exportar_esquema.py desde la base real
-- (preliquidacion) el 2026-09-08. Es el punto de partida para una base nueva: correr este
-- archivo y después las migraciones siguientes de la carpeta en orden.
-- NO editar a mano: regenerar con el script.

-- preliquidacion
CREATE TABLE IF NOT EXISTS `preliquidacion` (
  `id` int NOT NULL AUTO_INCREMENT,
  `quincena` date NOT NULL,
  `creado_por` int NOT NULL,
  `creado_en` datetime DEFAULT NULL,
  `valor_hora_pulv` decimal(12,2) DEFAULT NULL,
  `valor_hora_tractorista` decimal(12,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `quincena` (`quincena`),
  KEY `creado_por` (`creado_por`),
  CONSTRAINT `preliquidacion_ibfk_1` FOREIGN KEY (`creado_por`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- concepto_liquidacion
CREATE TABLE IF NOT EXISTS `concepto_liquidacion` (
  `id` int NOT NULL AUTO_INCREMENT,
  `quincena` date NOT NULL,
  `tarea_nombre` varchar(200) NOT NULL,
  `cliente_nombre` varchar(150) DEFAULT NULL,
  `finca_nombre` varchar(150) DEFAULT NULL,
  `codigo` int DEFAULT NULL,
  `unidad_base` enum('hsjornal','hsmaquina','tancadas','unidades','jornal_tope1','jornal_tope1_mas_excedente','fijo') NOT NULL,
  `precio` decimal(12,4) DEFAULT NULL,
  `tipo` enum('REMUNERATIVO','NO_REMUNERATIVO','JORNAL','BONO_BOLSON','OTRO','EXCENTO') NOT NULL DEFAULT 'OTRO',
  `heredado` tinyint(1) NOT NULL,
  `categoria` int DEFAULT NULL,
  `reemplaza_comun` tinyint(1) NOT NULL,
  `creado_en` datetime DEFAULT NULL,
  `supervisor_nombre` varchar(150) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_concepto_unif` (`quincena`,`tarea_nombre`,`cliente_nombre`,`finca_nombre`,`codigo`,`categoria`,`supervisor_nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- preliquidacion_linea
CREATE TABLE IF NOT EXISTS `preliquidacion_linea` (
  `id` int NOT NULL AUTO_INCREMENT,
  `preliquidacion_id` int NOT NULL,
  `planilla` varchar(100) DEFAULT NULL,
  `fecha_tarea` date DEFAULT NULL,
  `nombre_cliente` varchar(150) DEFAULT NULL,
  `nombre_finca` varchar(150) DEFAULT NULL,
  `nombre_tarea` varchar(200) DEFAULT NULL,
  `nombre_tractor` varchar(150) DEFAULT NULL,
  `legajo_campo` varchar(20) DEFAULT NULL,
  `nombre_empleado` varchar(150) DEFAULT NULL,
  `cuit` varchar(20) DEFAULT NULL,
  `nombre_supervisor` varchar(150) DEFAULT NULL,
  `nombre_capataz` varchar(150) DEFAULT NULL,
  `implemento` varchar(150) DEFAULT NULL,
  `unidades` decimal(10,2) DEFAULT NULL,
  `tancadas` decimal(10,2) DEFAULT NULL,
  `hsjornal` decimal(6,2) DEFAULT NULL,
  `hsmaquina` decimal(6,2) DEFAULT NULL,
  `cantidad` decimal(10,2) DEFAULT NULL,
  `empresa_asignada` varchar(50) DEFAULT NULL,
  `legajo_asignado` varchar(20) DEFAULT NULL,
  `grupo_pago_aplicado` varchar(50) DEFAULT NULL,
  `codigo_liquidacion` int DEFAULT NULL,
  `precio_a` decimal(12,4) DEFAULT NULL,
  `importe_base` decimal(14,2) DEFAULT NULL,
  `importe_total` decimal(14,2) DEFAULT NULL,
  `observacion` text,
  `es_duplicado` tinyint(1) DEFAULT NULL,
  `alerta_legajo` tinyint(1) DEFAULT NULL,
  `alerta_empresa` tinyint(1) DEFAULT NULL,
  `linea_incompleta` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_linea_tarea` (`preliquidacion_id`,`nombre_tarea`),
  KEY `ix_linea_cuit` (`preliquidacion_id`,`cuit`),
  KEY `ix_linea_orden` (`preliquidacion_id`,`empresa_asignada`,`nombre_empleado`,`fecha_tarea`),
  CONSTRAINT `preliquidacion_linea_ibfk_1` FOREIGN KEY (`preliquidacion_id`) REFERENCES `preliquidacion` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- concepto_adicional
CREATE TABLE IF NOT EXISTS `concepto_adicional` (
  `id` int NOT NULL AUTO_INCREMENT,
  `linea_id` int NOT NULL,
  `descripcion` varchar(150) NOT NULL,
  `codigo_concepto` int DEFAULT NULL,
  `tipo` enum('REMUNERATIVO','NO_REMUNERATIVO','JORNAL','BONO_BOLSON','OTRO','EXCENTO') DEFAULT 'OTRO',
  `unidad_base` varchar(30) DEFAULT NULL,
  `precio` decimal(12,4) DEFAULT NULL,
  `cantidad` decimal(10,2) DEFAULT NULL,
  `concepto_liquidacion_id` int DEFAULT NULL,
  `importe` decimal(12,2) NOT NULL,
  `ingresado_por` int DEFAULT NULL,
  `fecha` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `concepto_liquidacion_id` (`concepto_liquidacion_id`),
  KEY `ingresado_por` (`ingresado_por`),
  KEY `ix_concepto_linea_ingresado` (`linea_id`,`ingresado_por`),
  CONSTRAINT `concepto_adicional_ibfk_1` FOREIGN KEY (`linea_id`) REFERENCES `preliquidacion_linea` (`id`),
  CONSTRAINT `concepto_adicional_ibfk_2` FOREIGN KEY (`concepto_liquidacion_id`) REFERENCES `concepto_liquidacion` (`id`) ON DELETE SET NULL,
  CONSTRAINT `concepto_adicional_ibfk_3` FOREIGN KEY (`ingresado_por`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ajuste_manual
CREATE TABLE IF NOT EXISTS `ajuste_manual` (
  `id` int NOT NULL AUTO_INCREMENT,
  `linea_id` int NOT NULL,
  `campo_modificado` varchar(100) DEFAULT NULL,
  `valor_anterior` text,
  `valor_nuevo` text,
  `motivo` text,
  `usuario_id` int DEFAULT NULL,
  `fecha` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `linea_id` (`linea_id`),
  KEY `usuario_id` (`usuario_id`),
  CONSTRAINT `ajuste_manual_ibfk_1` FOREIGN KEY (`linea_id`) REFERENCES `preliquidacion_linea` (`id`),
  CONSTRAINT `ajuste_manual_ibfk_2` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- categoria_operario
CREATE TABLE IF NOT EXISTS `categoria_operario` (
  `id` int NOT NULL AUTO_INCREMENT,
  `quincena` date NOT NULL,
  `cuil` varchar(20) NOT NULL,
  `categoria` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_categoria_operario` (`quincena`,`cuil`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

