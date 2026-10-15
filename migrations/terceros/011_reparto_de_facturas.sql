-- terceros/011 — Una orden de facturación repartida entre varias empresas.
-- NO DIFERIBLE: el código de esta versión la lee y la escribe.
-- Aplicar UNA vez por base, junto con el deploy, DESPUÉS de la 008.
--
-- Pedido del usuario (2026-10-05): a algunos terceros se les pide que facturen
-- una parte a una empresa y otra parte a otra. La orden sigue siendo una sola;
-- lo que pasa a ser varias es la factura. Por eso la empresa y la factura salen
-- de `terceros_recibo` y van a una fila por empresa.
--
-- El pago no cambia: sigue siendo uno por orden.

CREATE TABLE terceros_recibo_factura (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    recibo_id        INT NOT NULL,
    empresa          VARCHAR(40) NOT NULL,
    -- Cuánto le factura el tercero a esta empresa. Con una sola empresa queda
    -- vacío mientras la orden está abierta: es el Total a facturar, que todavía
    -- puede cambiar. Al emitir se escribe.
    importe          DECIMAL(14, 2) NULL,

    -- La factura que mandó el tercero para esta empresa.
    numero           VARCHAR(40) NULL,
    fecha            DATE NULL,
    importe_factura  DECIMAL(14, 2) NULL,
    -- RECIBIDA, APROBADA o RECHAZADA.
    estado           VARCHAR(20) NULL,
    motivo           VARCHAR(255) NULL,

    CONSTRAINT fk_recibo_factura_recibo FOREIGN KEY (recibo_id) REFERENCES terceros_recibo (id),
    UNIQUE KEY uq_recibo_factura (recibo_id, empresa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Lo que ya estaba elegido o facturado. En producción la 008 corre justo antes
-- y esto no copia nada; en la base de prueba sí.
INSERT INTO terceros_recibo_factura
    (recibo_id, empresa, importe, numero, fecha, importe_factura, estado, motivo)
SELECT id, empresa,
       CASE WHEN emitido_en IS NOT NULL THEN total_a_facturar END,
       factura_numero, factura_fecha, factura_importe, factura_estado, factura_motivo
FROM terceros_recibo
WHERE empresa IS NOT NULL;

ALTER TABLE terceros_recibo
    DROP COLUMN empresa,
    DROP COLUMN factura_numero,
    DROP COLUMN factura_fecha,
    DROP COLUMN factura_importe,
    DROP COLUMN factura_estado,
    DROP COLUMN factura_motivo;
