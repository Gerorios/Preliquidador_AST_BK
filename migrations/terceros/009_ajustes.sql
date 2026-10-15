-- terceros/009 — Los ajustes del recibo y lo que llegó tarde (etapa 11).
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Dos cosas que el recibo necesitaba y que ningún sistema de origen trae:
--
--   1. El **ajuste**: una corrección con signo y con motivo sobre el recibo
--      abierto de un tercero. Por algo que ningún origen sabe («le devuelvo un
--      descuento mal hecho»), o por lo que cambió en un recibo ya emitido.
--   2. Lo que **llegó tarde** a un recibo ya emitido y se decidió dejar como
--      está. Sin esto el aviso volvería a aparecer cada vez.


CREATE TABLE terceros_ajuste (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    -- La quincena del recibo en el que se liquida.
    quincena         DATE NOT NULL,
    tercero          VARCHAR(150) NOT NULL,
    -- De qué es: viajes, servicio, combustible, repuestos, reparacion u otro.
    -- Es lo que permite que el recibo diga «Ajuste combustible».
    concepto         VARCHAR(20) NOT NULL,
    -- Con signo, a favor del tercero: positivo se le paga más, negativo se le
    -- descuenta.
    importe          DECIMAL(14, 2) NOT NULL,
    -- Obligatorio: es lo que el tercero lee en el recibo.
    motivo           VARCHAR(255) NOT NULL,
    -- Si corrige algo de antes, de qué quincena.
    quincena_origen  DATE NULL,
    -- Si corrige una línea de un recibo emitido, cuál: «viajes:123», o
    -- «repuestos:45:2 de 3» si era una cuota. Es lo que hace que el aviso de
    -- esa línea se dé por resuelto.
    origen_clave     VARCHAR(60) NULL,
    creado_en        DATETIME NOT NULL,
    creado_por       INT NULL,
    CONSTRAINT fk_ajuste_usuario FOREIGN KEY (creado_por) REFERENCES usuarios (id),
    KEY ix_ajuste_recibo (quincena, tercero),
    KEY ix_ajuste_origen (quincena_origen, tercero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Lo que llegó tarde a un recibo emitido y se decidió no mover ni ajustar.
CREATE TABLE terceros_llegada_descartada (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    -- La quincena del recibo emitido al que llegó tarde.
    quincena    DATE NOT NULL,
    tercero     VARCHAR(150) NOT NULL,
    -- La línea, con la misma forma que `terceros_ajuste.origen_clave`.
    clave       VARCHAR(60) NOT NULL,
    motivo      VARCHAR(255) NOT NULL,
    creado_en   DATETIME NOT NULL,
    creado_por  INT NULL,
    CONSTRAINT fk_descartada_usuario FOREIGN KEY (creado_por) REFERENCES usuarios (id),
    UNIQUE KEY uq_descartada (quincena, tercero, clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
