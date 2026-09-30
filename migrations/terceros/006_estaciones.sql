-- terceros/006 — Estaciones de servicio (etapa 10).
-- NO DIFERIBLE: el código de esta versión escribe estas tablas.
-- Aplicar UNA vez por base, junto con el deploy.
--
-- Hasta acá el módulo sabía cuánto combustible se cargó **según el sistema de
-- campo**. Esto trae lo que la estación **facturó**, para poder cruzarlos: una
-- carga que la estación cobró y nadie registró es plata que la empresa pagó y
-- no le descontó a nadie.
--
-- El puente es el número de vale. Medido sobre agosto: donde cruza, cruza
-- perfecto — los 14 vales de YPF OASIS ALDERETE coinciden en litros al decimal.
--
-- ─── Por qué una tabla de estaciones y no una constante ────────────────────
--
-- Tres razones que salieron de mirar los archivos reales:
--
--   1. **El nombre no coincide.** El archivo se llama "Calchaqui" y en el
--      sistema de campo esa estación es `YPF OASIS ALDERETE`; "Garsa" es
--      `GAR S.A.`. Sin esta traducción, cruzar por nombre no da nunca.
--
--   2. **Cada una manda un layout distinto.** Calchaqui y Oasis vienen del
--      mismo sistema (45 columnas, el vale en `NumVehiculo`); Garsa es otro
--      mundo: el vale en `ORDEN_CARGA`, la cantidad en negativo y la fecha
--      como serial de Excel. El mapeo se configura una vez y queda.
--
--   3. **La Angostura no manda archivo**: llega por foto. Sus cargas se
--      tipean, y por eso `archivo` es opcional.
--
-- Y una que apareció después: **Shell Famaillá, que es la más grande, no manda
-- el número de vale**. Las 104 líneas de agosto traen `NumVehiculo` vacío. Su
-- mapeo se deja igual apuntando a esa columna: el día que la llenen, cruza
-- sola. Mientras tanto sus cargas se encuentran por patente y litros.
--
-- `mapeo` es JSON y no columnas porque lo que cambia entre estaciones es
-- justamente qué campos hay y cómo se llaman. Una columna por cada nombre
-- posible sería una tabla que crece con cada estación nueva.

CREATE TABLE terceros_estacion (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    -- Cómo la llamamos nosotros. Es el que se ve en la pantalla.
    nombre            VARCHAR(150) NOT NULL,
    -- El nombre EXACTO que tiene en `laa_combustiblesorigen` del sistema de
    -- campo. Es lo que ata sus líneas con nuestras cargas.
    --
    -- Nulo mientras no se sepa: La Angostura no aparece en ese maestro con
    -- ningún nombre, y hasta que alguien diga bajo cuál se registran sus
    -- cargas, inventarle uno sería cruzar contra nada.
    origen_campo      VARCHAR(150) NULL,
    -- Cómo leer su archivo. NULL en la que no manda archivo.
    mapeo             JSON NULL,
    -- Una estación que dejó de operar no se borra: sus cargas viejas siguen
    -- teniendo que poder mirarse.
    activa            TINYINT(1) NOT NULL DEFAULT 1,
    creado_en         DATETIME NOT NULL,
    UNIQUE KEY uq_terceros_estacion_origen (origen_campo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Una línea de lo que la estación facturó. No es un hecho de la quincena: es
-- la contraparte contra la que se cruzan los hechos.
CREATE TABLE terceros_carga_facturada (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    estacion_id    INT NOT NULL,
    -- De qué quincena es, para no tener que mirar el año entero al cruzar.
    quincena       DATE NOT NULL,
    fecha          DATE NULL,
    -- El puente. Sin esto la línea no se puede cruzar con nada, y se guarda
    -- igual: que la estación cobre algo sin vale también hay que verlo.
    vale           VARCHAR(30) NULL,
    litros         DECIMAL(12, 2) NULL,
    importe        DECIMAL(14, 2) NULL,
    -- Diesel o nafta. Decide si la línea corresponde a un colectivo o a la
    -- flota liviana, que queda afuera de la liquidación.
    producto       VARCHAR(80) NULL,
    patente        VARCHAR(30) NULL,
    chofer         VARCHAR(150) NULL,
    -- De qué archivo salió, para poder rastrear una línea hasta su papel.
    archivo        VARCHAR(255) NULL,
    subido_en      DATETIME NOT NULL,
    subido_por     INT NULL,
    CONSTRAINT fk_facturada_estacion FOREIGN KEY (estacion_id)
        REFERENCES terceros_estacion (id),
    CONSTRAINT fk_facturada_usuario FOREIGN KEY (subido_por)
        REFERENCES usuarios (id),
    KEY ix_facturada_quincena (quincena, estacion_id),
    -- Para el cruce, que es por vale.
    KEY ix_facturada_vale (vale)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Las tres que mandan archivo más la que no.
--
-- La correspondencia con el sistema de campo **está medida, no informada**: los
-- 14 vales del archivo de Calchaqui que cruzan están todos registrados como
-- `YPF OASIS ALDERETE`, y coinciden en litros al decimal. Existe además un
-- origen llamado `CALCHAQUI` en el maestro, pero no se usó ni una vez en 2026.
-- Si alguien confirma otra cosa, se cambia acá: por eso es una fila y no una
-- constante en el código.
INSERT INTO terceros_estacion (nombre, origen_campo, mapeo, activa, creado_en) VALUES
  ('Calchaqui', 'YPF OASIS ALDERETE',
   '{"hoja": "Sheet", "fila_encabezado": 1, "columnas": {"fecha": "Fecha", "vale": "NumVehiculo", "litros": "CantidadDetalle", "importe": "TotalDetalle", "producto": "Articulo", "patente": "Patente", "chofer": "Chofer"}}',
   1, NOW()),
  ('Garsa', 'GAR S.A.',
   '{"hoja": "SQL Results", "fila_encabezado": 1, "fecha_serial": true, "valor_absoluto": ["litros"], "columnas": {"fecha": "FECHA", "vale": "ORDEN_CARGA", "litros": "CANTIDAD", "importe": "IMPORTE", "producto": "PRODUCTOS", "patente": "PATENTE", "chofer": "CONDUCTOR"}}',
   1, NOW()),
  ('Shell Famaillá', 'SHELL FAMAILLA',
   '{"hoja": "Sheet", "fila_encabezado": 1, "fecha_serial": true, "columnas": {"fecha": "Fecha", "vale": "NumVehiculo", "litros": "CantidadDetalle", "importe": "TotalDetalle", "producto": "Articulo", "patente": "Patente", "chofer": "Chofer"}}',
   1, NOW()),
  ('La Angostura', NULL, NULL, 1, NOW());
