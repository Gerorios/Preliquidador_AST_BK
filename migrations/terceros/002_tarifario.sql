-- terceros/002 — El Tarifario (etapa 6 del plan).
-- NO DIFERIBLE: sin estas tablas no se le puede poner precio a nada.
-- Aplicar UNA vez por base, junto con el deploy de la etapa 6.
--
-- Cinco tablas, una por cada cosa que se paga o se descuenta. Todas son **por
-- quincena** y ninguna se deriva de los datos: cada precio se pacta con cada
-- tercero (ver CONTEXT-terceros.md, "Tarifario").
--
-- SIN DIMENSIÓN SE GUARDA COMO '' Y NO COMO NULL. Es la decisión menos obvia de
-- esta migración y tiene un motivo concreto: en MySQL un UNIQUE deja pasar
-- varias filas con NULL, así que con dimensiones nullable se podrían cargar dos
-- reglas idénticas. Dos reglas idénticas es justo el empate que el módulo no
-- sabe resolver —queda ambiguo y lo tiene que destrabar una persona—, y peor
-- todavía si nadie se entera de que están duplicadas. Con '' el índice único
-- hace su trabajo. La contra es que 'sin dimensión' se lee como cadena vacía en
-- vez de NULL; se banca a cambio de que la base no permita el duplicado.
--
-- La regla más específica es la que tiene más dimensiones cargadas: se cuenta
-- cuántas son distintas de ''.

-- ─── Lo que se le paga ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS terceros_tarifa_viaje (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    quincena    DATE         NOT NULL,
    -- Las cuatro dimensiones. '' = la regla no discrimina por eso.
    tercero     VARCHAR(150) NOT NULL DEFAULT '',
    cliente     VARCHAR(150) NOT NULL DEFAULT '',
    finca       VARCHAR(150) NOT NULL DEFAULT '',
    capataz     VARCHAR(150) NOT NULL DEFAULT '',
    -- El tipo no es clave de la tarifa sino su resultado: la misma regla que
    -- fija el precio fija si el viaje es corto o largo.
    tipo_viaje  VARCHAR(10)  NULL,
    precio      DECIMAL(14,2) NOT NULL,
    -- Vino copiada de otra quincena y nadie la confirmó todavía. Paga igual,
    -- pero se resalta para no arrastrar un precio viejo sin darse cuenta.
    heredada    TINYINT(1)   NOT NULL DEFAULT 0,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por  INT          NULL,
    UNIQUE KEY uq_terceros_tarifa_viaje (quincena, tercero, cliente, finca, capataz),
    KEY ix_terceros_tarifa_viaje_quincena (quincena),
    CONSTRAINT fk_terceros_tarifa_viaje_usuario
        FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_tarifa_servicio (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    quincena    DATE         NOT NULL,
    tercero     VARCHAR(150) NOT NULL DEFAULT '',
    cliente     VARCHAR(150) NOT NULL DEFAULT '',
    finca       VARCHAR(150) NOT NULL DEFAULT '',
    tarea       VARCHAR(200) NOT NULL DEFAULT '',
    -- Sobre qué medida se calcula: 'hsmaquina' o 'unidades'. Son los mismos
    -- valores que la Unidad base de Preliquidación, a propósito.
    unidad_base VARCHAR(20)  NOT NULL,
    precio      DECIMAL(14,2) NOT NULL,
    heredada    TINYINT(1)   NOT NULL DEFAULT 0,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por  INT          NULL,
    UNIQUE KEY uq_terceros_tarifa_servicio (quincena, tercero, cliente, finca, tarea),
    KEY ix_terceros_tarifa_servicio_quincena (quincena),
    CONSTRAINT fk_terceros_tarifa_servicio_usuario
        FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─── Lo que se le descuenta ─────────────────────────────────────────────────

-- Estas tres no necesitan "regla más específica": tienen una sola combinación
-- posible por tercero, así que o hay tarifa o no hay.

CREATE TABLE IF NOT EXISTS terceros_precio_combustible (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    quincena    DATE         NOT NULL,
    tercero     VARCHAR(150) NOT NULL,
    precio      DECIMAL(14,4) NOT NULL,      -- por litro: admite más decimales
    heredada    TINYINT(1)   NOT NULL DEFAULT 0,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por  INT          NULL,
    UNIQUE KEY uq_terceros_precio_combustible (quincena, tercero),
    KEY ix_terceros_precio_combustible_quincena (quincena),
    CONSTRAINT fk_terceros_precio_combustible_usuario
        FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_precio_reparacion (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    quincena    DATE         NOT NULL,
    tercero     VARCHAR(150) NOT NULL,
    precio      DECIMAL(14,2) NOT NULL,      -- por hora de mano de obra
    heredada    TINYINT(1)   NOT NULL DEFAULT 0,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por  INT          NULL,
    UNIQUE KEY uq_terceros_precio_reparacion (quincena, tercero),
    KEY ix_terceros_precio_reparacion_quincena (quincena),
    CONSTRAINT fk_terceros_precio_reparacion_usuario
        FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_precio_seguro (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    quincena    DATE         NOT NULL,
    tercero     VARCHAR(150) NOT NULL,
    maquinaria  VARCHAR(200) NOT NULL,
    importe     DECIMAL(14,2) NOT NULL,      -- la cuota, no un precio unitario
    heredada    TINYINT(1)   NOT NULL DEFAULT 0,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por  INT          NULL,
    UNIQUE KEY uq_terceros_precio_seguro (quincena, tercero, maquinaria),
    KEY ix_terceros_precio_seguro_quincena (quincena),
    CONSTRAINT fk_terceros_precio_seguro_usuario
        FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─── Vuelta atrás ───────────────────────────────────────────────────────────
--
-- DROP TABLE IF EXISTS terceros_precio_seguro;
-- DROP TABLE IF EXISTS terceros_precio_reparacion;
-- DROP TABLE IF EXISTS terceros_precio_combustible;
-- DROP TABLE IF EXISTS terceros_tarifa_servicio;
-- DROP TABLE IF EXISTS terceros_tarifa_viaje;
