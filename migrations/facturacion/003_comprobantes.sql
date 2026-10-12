-- facturacion/003 — Comprobantes, sus Líneas y sus Adjuntos (E2).
-- NO DIFERIBLE: el código de esta versión las lee y las escribe.
-- Aplicar UNA vez por base, junto con el deploy. Idempotente: si una tabla ya existe, no hace nada.
--
-- Un Comprobante es una Factura o una Nota de crédito emitida a un Cliente. Se
-- carga a mano o llega de la migración del histórico (la planilla de las
-- contadoras). El Cliente y la Tarea se guardan por id del sistema de campo,
-- con una copia del nombre: el listado no lee la base de campo.
--
-- clave_identidad la calcula el servicio y la base la hace cumplir. Hace falta
-- porque el histórico no tiene Empresa, MySQL acepta varios NULL en un UNIQUE y
-- en la planilla el mismo número aparece para dos Clientes. Tres formas:
-- E|empresa|tipo|numero a mano (Facturas y Notas de crédito numeran aparte),
-- H|cliente_id|numero en un histórico (siempre una Factura) y
-- S|cliente_id|fecha a facturar en un histórico sin número. De ella depende que
-- la migración del histórico se pueda correr varias veces sin duplicar.
--
-- Las Líneas caen con su Comprobante (ON DELETE CASCADE). Los Adjuntos no: los
-- borra el servicio junto con sus archivos, y el DELETE de vuelta atrás de los
-- históricos falla si alguno ya tiene adjunto, que es lo que se quiere.
--
-- Vuelta atrás (sólo si no hay datos reales, el código viejo convive con las tablas),
-- en este orden. Con datos reales, restaurar el respaldo tomado antes.
-- DROP TABLE facturacion_adjunto
-- DROP TABLE facturacion_linea
-- DROP TABLE facturacion_comprobante

CREATE TABLE IF NOT EXISTS facturacion_comprobante (
    id                     INT           AUTO_INCREMENT PRIMARY KEY,
    -- factura o nota_credito.
    tipo                   VARCHAR(20)   NOT NULL,
    -- El id del maestro de clientes del sistema de campo.
    cliente_id             INT           NOT NULL,
    -- Copia al guardar.
    cliente_nombre         VARCHAR(150)  NOT NULL,
    -- Vacía sólo en un histórico.
    empresa_emisora        VARCHAR(100)  NULL,
    -- Normalizado. Vacío sólo en un histórico sin número.
    numero                 VARCHAR(30)   NULL,
    -- Vacía sólo en un histórico sin FECHA FAC.
    fecha                  DATE          NULL,
    -- Obligatoria en una Nota de crédito cargada a mano. Sin ON DELETE: una
    -- Factura con Notas de crédito no se borra.
    factura_corregida_id   INT           NULL,
    es_historico           TINYINT(1)    NOT NULL DEFAULT 0,
    -- Sólo en un histórico sin número posterior al corte: el Cruce (E3) no
    -- cuenta sus Líneas como facturado.
    pendiente_de_facturar  TINYINT(1)    NOT NULL DEFAULT 0,
    clave_identidad        VARCHAR(160)  NOT NULL,
    creado_en              DATETIME      NOT NULL,
    -- NULL = lo creó la migración del histórico, no una persona.
    creado_por             INT           NULL,
    -- NULL = nunca se editó.
    actualizado_en         DATETIME      NULL,
    actualizado_por        INT           NULL,
    UNIQUE KEY uq_facturacion_comprobante_clave (clave_identidad),
    KEY ix_facturacion_comprobante_cliente_numero (cliente_id, numero),
    KEY ix_facturacion_comprobante_fecha (fecha),
    CONSTRAINT fk_facturacion_comprobante_corregida FOREIGN KEY (factura_corregida_id)
        REFERENCES facturacion_comprobante (id),
    CONSTRAINT fk_facturacion_comprobante_creado_por FOREIGN KEY (creado_por)
        REFERENCES usuarios (id) ON DELETE SET NULL,
    CONSTRAINT fk_facturacion_comprobante_actualizado_por FOREIGN KEY (actualizado_por)
        REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- Una Línea: qué tarea, cuánto y a qué precio. El importe es siempre >= 0, el
-- signo lo da el tipo del Comprobante, como en Terceros.
CREATE TABLE IF NOT EXISTS facturacion_linea (
    id                INT            AUTO_INCREMENT PRIMARY KEY,
    comprobante_id    INT            NOT NULL,
    orden             SMALLINT       NOT NULL,
    -- La fecha a facturar (el 1 o el 16), no la del Comprobante.
    fecha             DATE           NOT NULL,
    -- El id de la tarea en el sistema de campo, con una copia del nombre.
    tarea_id          INT            NOT NULL,
    tarea_nombre      VARCHAR(150)   NOT NULL,
    -- Una de las nueve claves de app/modulos/facturacion/unidades.py.
    unidad            VARCHAR(20)    NOT NULL,
    -- Las dos o ninguna.
    finca_id          INT            NULL,
    finca_nombre      VARCHAR(150)   NULL,
    cantidad          DECIMAL(14, 2) NOT NULL,
    precio_unitario   DECIMAL(14, 4) NOT NULL,
    importe           DECIMAL(14, 2) NOT NULL,
    KEY ix_facturacion_linea_comprobante (comprobante_id),
    -- Para el Cruce de la E3, que busca por tarea y fecha.
    KEY ix_facturacion_linea_tarea_fecha (tarea_id, fecha),
    CONSTRAINT fk_facturacion_linea_comprobante FOREIGN KEY (comprobante_id)
        REFERENCES facturacion_comprobante (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- Un PDF o una imagen de un Comprobante, en la carpeta de adjuntos del VPS
-- (ADR-0019). El nombre en disco lo genera el sistema y el tipo es el
-- detectado por contenido.
CREATE TABLE IF NOT EXISTS facturacion_adjunto (
    id                INT            AUTO_INCREMENT PRIMARY KEY,
    -- Sin cascada a propósito: ver el encabezado.
    comprobante_id    INT            NOT NULL,
    -- Saneado, sólo para mostrar.
    nombre_original   VARCHAR(255)   NOT NULL,
    nombre_en_disco   VARCHAR(64)    NOT NULL,
    tipo_contenido    VARCHAR(50)    NOT NULL,
    tamano_bytes      INT            NOT NULL,
    subido_en         DATETIME       NOT NULL,
    subido_por        INT            NULL,
    UNIQUE KEY uq_facturacion_adjunto_nombre_en_disco (nombre_en_disco),
    CONSTRAINT fk_facturacion_adjunto_comprobante FOREIGN KEY (comprobante_id)
        REFERENCES facturacion_comprobante (id),
    CONSTRAINT fk_facturacion_adjunto_subido_por FOREIGN KEY (subido_por)
        REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
