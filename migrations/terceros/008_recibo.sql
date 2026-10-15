-- terceros/008 — El recibo, la factura, el pago y el saldo (etapa 11).
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Hasta acá cada quincena se calculaba en vivo, y eso está bien mientras nadie
-- la haya mandado. **Emitir el recibo lo congela**: lo que se le mandó a un
-- tercero no puede cambiar solo porque alguien corrigió un dato viejo en el
-- origen. Pasó: una hora de taller de una quincena ya liquidada desapareció del
-- Sheet entre el 9 y el 14 de septiembre.
--
-- Por eso el recibo guarda una FOTO (`contenido`) y no se vuelve a armar: la
-- foto es lo que el tercero recibió.

CREATE TABLE terceros_recibo (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    quincena          DATE NOT NULL,
    tercero           VARCHAR(150) NOT NULL,

    -- La emisión. La fila nace al emitir; reabrir borra la foto y deja la fila,
    -- con la factura y su historia.
    emitido_en        DATETIME NULL,
    emitido_por       INT NULL,
    -- A quién le factura esta quincena. Cambia de una quincena a otra, por eso
    -- va acá y no en un maestro de terceros.
    empresa           VARCHAR(40) NULL,
    -- Los bloques con sus líneas, tal como se emitieron.
    contenido         JSON NULL,
    total_a_facturar  DECIMAL(14, 2) NULL,
    seguros           DECIMAL(14, 2) NULL,
    total_a_pagar     DECIMAL(14, 2) NULL,
    saldo_anterior    DECIMAL(14, 2) NULL,

    -- Una quincena en discusión con el tercero no suma al saldo acumulado: se
    -- muestra aparte, para que no se olvide sin ensuciar el número.
    en_revision       TINYINT(1) NOT NULL DEFAULT 0,
    motivo_revision   VARCHAR(255) NULL,

    -- La factura del tercero. El archivo no se guarda todavía: dónde guardar
    -- archivos es una decisión de infraestructura pendiente.
    factura_numero    VARCHAR(40) NULL,
    factura_fecha     DATE NULL,
    factura_importe   DECIMAL(14, 2) NULL,
    -- RECIBIDA, APROBADA o RECHAZADA.
    factura_estado    VARCHAR(20) NULL,
    factura_motivo    VARCHAR(255) NULL,

    -- El pago. TOTAL asume todo lo que se le debía; PARCIAL pide el importe.
    -- El importe se guarda en los dos casos: el saldo se arma sumando esto, y
    -- «total» sin número dejaría el saldo dependiendo de cuándo se lo mire.
    pago              VARCHAR(10) NULL,
    pago_importe      DECIMAL(14, 2) NULL,
    pago_fecha        DATE NULL,

    CONSTRAINT fk_recibo_emitido_por FOREIGN KEY (emitido_por) REFERENCES usuarios (id),
    UNIQUE KEY uq_recibo (quincena, tercero),
    KEY ix_recibo_tercero (tercero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Cada cosa que le pasa a un recibo, con quién y por qué. Es el registro de
-- auditoría que pide el plan: sin esto, un recibo reabierto y vuelto a emitir
-- no deja rastro de que alguna vez dijo otra cosa.
CREATE TABLE terceros_recibo_evento (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    recibo_id   INT NOT NULL,
    -- EMITIDO, REABIERTO, FACTURA, APROBADA, RECHAZADA, PAGO, REVISION.
    tipo        VARCHAR(20) NOT NULL,
    motivo      VARCHAR(255) NULL,
    -- Lo que cambió, para poder leer el evento sin reconstruirlo.
    detalle     JSON NULL,
    creado_en   DATETIME NOT NULL,
    creado_por  INT NULL,
    CONSTRAINT fk_evento_recibo FOREIGN KEY (recibo_id) REFERENCES terceros_recibo (id),
    CONSTRAINT fk_evento_usuario FOREIGN KEY (creado_por) REFERENCES usuarios (id),
    KEY ix_evento_recibo (recibo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Con qué saldo arranca cada tercero. El módulo no importa el Excel: el saldo
-- que traía se carga a mano una vez, y después se arrastra solo.
--
-- Positivo, la empresa le debe al tercero; negativo, el tercero le debe.
CREATE TABLE terceros_saldo_inicial (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    tercero     VARCHAR(150) NOT NULL,
    -- La primera quincena que se liquida en el módulo. El saldo es el que
    -- traía ANTES de ella; lo de quincenas anteriores no se suma.
    quincena    DATE NOT NULL,
    importe     DECIMAL(14, 2) NOT NULL,
    motivo      VARCHAR(255) NULL,
    creado_en   DATETIME NOT NULL,
    creado_por  INT NULL,
    CONSTRAINT fk_saldo_usuario FOREIGN KEY (creado_por) REFERENCES usuarios (id),
    UNIQUE KEY uq_saldo_tercero (tercero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
