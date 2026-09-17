-- terceros/001 — Las tablas del módulo Liquidación Terceros (etapa 5 del plan).
-- NO DIFERIBLE: sin estas tablas el módulo no puede generar una quincena.
-- Aplicar UNA vez por base, junto con el deploy de la etapa 5.
--
-- Qué guardan: la foto de lo que las cinco fuentes tenían cuando se generó la
-- quincena. Hasta ahora el módulo leía los orígenes en vivo en cada request, y
-- por eso los números se movían entre una pantalla y otra.
--
-- Los precios NO están acá a propósito: se calculan en la etapa 7 y van con su
-- propia migración, junto con el código que los necesita.
--
-- Todas las tablas de hechos comparten dos columnas manuales:
--   quincena_efectiva + motivo_efectiva  — la quincena en la que el hecho se
--     cobra de verdad, cuando no es la de su fecha (ver CONTEXT-terceros.md).
-- Son "trabajo manual": al regenerar una quincena, las filas que las tienen
-- cargadas se protegen y se borran últimas.

-- ─── La quincena generada ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS terceros_liquidacion (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    quincena       DATE     NOT NULL,           -- su primer día: el 1 o el 16
    generada_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    generada_por   INT      NULL,
    actualizada_en DATETIME NULL,               -- última vez que se reconcilió
    UNIQUE KEY uq_terceros_liquidacion_quincena (quincena),
    CONSTRAINT fk_terceros_liquidacion_usuario
        FOREIGN KEY (generada_por) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─── Lo que se le paga ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS terceros_viaje (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    liquidacion_id    INT          NOT NULL,
    -- El dueño del colectivo. En el sistema de campo el `nombre` del colectivo
    -- es, en realidad, el nombre de su dueño: por eso se guardan los dos.
    tercero           VARCHAR(150) NULL,
    colectivo_nombre  VARCHAR(150) NULL,
    colectivo_patente VARCHAR(30)  NULL,
    fecha_uso         DATE         NULL,
    fecha_carga       DATE         NULL,
    cliente           VARCHAR(150) NULL,
    finca             VARCHAR(150) NULL,
    tarea             VARCHAR(200) NULL,
    supervisor        VARCHAR(150) NULL,
    capataz           VARCHAR(150) NULL,
    chofer            VARCHAR(150) NULL,
    cantidad_viajes   DECIMAL(12,2) NULL,       -- 0,5 es normal: medio viaje
    cant_personas     INT          NULL,
    quincena_efectiva DATE         NULL,
    motivo_efectiva   VARCHAR(255) NULL,
    KEY ix_terceros_viaje_liquidacion (liquidacion_id),
    KEY ix_terceros_viaje_tercero (tercero),
    CONSTRAINT fk_terceros_viaje_liquidacion
        FOREIGN KEY (liquidacion_id) REFERENCES terceros_liquidacion(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_hora_servicio (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    liquidacion_id    INT          NOT NULL,
    tercero           VARCHAR(150) NULL,        -- NULL: la descripción traía una patente
    fecha             DATE         NULL,
    planilla          VARCHAR(20)  NULL,        -- COSECHA | MAQUINARIA | PULVERIZADA
    cliente           VARCHAR(150) NULL,
    finca             VARCHAR(150) NULL,
    tarea             VARCHAR(200) NULL,
    maquinaria        VARCHAR(200) NULL,
    supervisor        VARCHAR(150) NULL,
    -- Las dos medidas sobre las que se puede pactar. Cuál se paga lo decide la
    -- Unidad base de la tarifa, no el dato.
    horas_maquina     DECIMAL(10,2) NULL,
    unidades          DECIMAL(12,2) NULL,       -- sólo la planilla de MAQUINARIA
    unidad            VARCHAR(30)  NULL,        -- BINS, TANCADAS, HORAS… informativa
    quincena_efectiva DATE         NULL,
    motivo_efectiva   VARCHAR(255) NULL,
    KEY ix_terceros_hora_servicio_liquidacion (liquidacion_id),
    KEY ix_terceros_hora_servicio_tercero (tercero),
    CONSTRAINT fk_terceros_hora_servicio_liquidacion
        FOREIGN KEY (liquidacion_id) REFERENCES terceros_liquidacion(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─── Lo que se le descuenta ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS terceros_carga_combustible (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    liquidacion_id    INT          NOT NULL,
    tercero           VARCHAR(150) NULL,
    colectivo_nombre  VARCHAR(150) NULL,
    colectivo_patente VARCHAR(30)  NULL,
    fecha_uso         DATE         NULL,
    fecha_carga       DATE         NULL,
    litros            DECIMAL(12,2) NULL,
    -- El número del comprobante físico. Es la clave con la que después se
    -- concilia contra lo que factura cada estación.
    vale              VARCHAR(30)  NULL,
    origen            VARCHAR(150) NULL,
    usuario_carga     VARCHAR(150) NULL,
    quincena_efectiva DATE         NULL,
    motivo_efectiva   VARCHAR(255) NULL,
    KEY ix_terceros_combustible_liquidacion (liquidacion_id),
    KEY ix_terceros_combustible_tercero (tercero),
    KEY ix_terceros_combustible_vale (vale),
    CONSTRAINT fk_terceros_combustible_liquidacion
        FOREIGN KEY (liquidacion_id) REFERENCES terceros_liquidacion(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_repuesto (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    liquidacion_id    INT          NOT NULL,
    tercero           VARCHAR(150) NULL,
    id_maquina        INT          NULL,        -- el id del sistema de compras
    maquina           VARCHAR(200) NULL,
    -- La del encabezado del movimiento, que es la que hoy decide la quincena.
    fecha             DATE         NULL,
    -- La de la descarga a la maquinaria, que es la correcta. Se guardan las dos
    -- para poder medir el desvío antes de cambiar el criterio (plan, sección 4).
    fecha_descarga    DATE         NULL,
    tipo_insumo       VARCHAR(60)  NULL,
    rubro             VARCHAR(100) NULL,
    repuesto          VARCHAR(200) NULL,
    cantidad          DECIMAL(12,2) NULL,
    precio_unitario   DECIMAL(14,4) NULL,       -- viene del sistema de compras
    monto_total       DECIMAL(14,4) NULL,       -- ídem: no lo calcula el módulo
    reparacion        VARCHAR(1)   NULL,
    proveedor         VARCHAR(150) NULL,
    -- Marca manual: hay salidas que no se le cobran al tercero (plan, 3.5).
    no_cobrar         TINYINT(1)   NOT NULL DEFAULT 0,
    motivo_no_cobrar  VARCHAR(255) NULL,
    quincena_efectiva DATE         NULL,
    motivo_efectiva   VARCHAR(255) NULL,
    KEY ix_terceros_repuesto_liquidacion (liquidacion_id),
    KEY ix_terceros_repuesto_tercero (tercero),
    CONSTRAINT fk_terceros_repuesto_liquidacion
        FOREIGN KEY (liquidacion_id) REFERENCES terceros_liquidacion(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS terceros_hora_reparacion (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    liquidacion_id    INT          NOT NULL,
    tercero           VARCHAR(150) NULL,
    id_maquina        INT          NULL,        -- el id de la app del taller
    maquina           VARCHAR(200) NULL,
    tipo_maquina      VARCHAR(60)  NULL,
    fecha             DATE         NULL,
    rubro             VARCHAR(100) NULL,
    sub_rubro         VARCHAR(200) NULL,
    finca             VARCHAR(150) NULL,
    lugar             VARCHAR(150) NULL,
    -- Aprobado o Pendiente. Sólo se cobran las aprobadas. Las rechazadas ni
    -- siquiera llegan acá, porque no se cobran nunca.
    estado            VARCHAR(30)  NULL,
    horas             DECIMAL(10,2) NULL,
    horas_preparacion DECIMAL(10,2) NULL,
    horas_traslado    DECIMAL(10,2) NULL,
    horas_total       DECIMAL(10,2) NULL,
    quincena_efectiva DATE         NULL,
    motivo_efectiva   VARCHAR(255) NULL,
    KEY ix_terceros_hora_reparacion_liquidacion (liquidacion_id),
    KEY ix_terceros_hora_reparacion_tercero (tercero),
    CONSTRAINT fk_terceros_hora_reparacion_liquidacion
        FOREIGN KEY (liquidacion_id) REFERENCES terceros_liquidacion(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─── Vuelta atrás ───────────────────────────────────────────────────────────
-- Las cinco tablas de hechos primero, la cabecera al final por las FK.
--
-- DROP TABLE IF EXISTS terceros_hora_reparacion;
-- DROP TABLE IF EXISTS terceros_repuesto;
-- DROP TABLE IF EXISTS terceros_carga_combustible;
-- DROP TABLE IF EXISTS terceros_hora_servicio;
-- DROP TABLE IF EXISTS terceros_viaje;
-- DROP TABLE IF EXISTS terceros_liquidacion;
