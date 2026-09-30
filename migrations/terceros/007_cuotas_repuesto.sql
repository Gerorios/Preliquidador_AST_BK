-- terceros/007 — Los repuestos que se descuentan en cuotas.
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Un repuesto caro no siempre se le descuenta entero al tercero en la quincena
-- en que salió: a veces se le reparte en cuotas quincenales iguales. Hasta acá
-- el módulo sólo sabía mover un hecho entero a otra quincena
-- (`quincena_efectiva`); esto lo reparte en varias.
--
-- Una fila por cuota, con el importe escrito, y no el importe dividido al
-- vuelo en cada lectura. Porque una cuota emitida es un cobro, y lo que un
-- tercero ya saldó no se mueve solo: si la cuota se derivara del repuesto, una
-- corrección en el sistema de compras cambiaría cuotas que ya se le cobraron.
--
-- La última cuota absorbe el redondeo, para que la suma dé exacta el importe
-- del repuesto al centavo.

CREATE TABLE terceros_cuota_repuesto (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    repuesto_id  INT NOT NULL,
    -- «cuota 2 de 5»: el recibo lo muestra así, y sin el total no se sabe
    -- cuánto le falta al tercero.
    numero       SMALLINT NOT NULL,
    de           SMALLINT NOT NULL,
    -- En qué quincena se descuenta esta cuota.
    quincena     DATE NOT NULL,
    importe      DECIMAL(14, 2) NOT NULL,
    -- Por qué se le financió. Opcional: «cuota 2 de 5» ya se explica sola en
    -- el recibo, a diferencia de un hecho movido de quincena.
    motivo       VARCHAR(255) NULL,
    creado_en    DATETIME NOT NULL,
    creado_por   INT NULL,
    CONSTRAINT fk_cuota_repuesto FOREIGN KEY (repuesto_id)
        REFERENCES terceros_repuesto (id),
    CONSTRAINT fk_cuota_usuario FOREIGN KEY (creado_por)
        REFERENCES usuarios (id),
    UNIQUE KEY uq_cuota_repuesto (repuesto_id, numero),
    KEY ix_cuota_quincena (quincena)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
