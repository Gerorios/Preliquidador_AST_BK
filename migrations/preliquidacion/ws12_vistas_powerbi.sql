-- ─────────────────────────────────────────────────────────────────────────────
-- WS12 — Vistas de reporting para Power BI
-- Base: db_propia (sistema de preliquidación).
--
-- Dos vistas de SOLO LECTURA para que Power BI consuma la preliquidación sin
-- query nativo embebido (habilita query folding y centraliza la lógica):
--
--   vw_bi_lineas            grano: 1 fila = 1 tarea de campo (línea).
--                           Cantidades físicas (horas, tancadas, unidades)
--                           viven acá y NO se duplican por concepto.
--   vw_bi_conceptos_pagados grano: 1 fila = 1 hecho de pago (snapshot
--                           congelado de concepto_adicional). Los importes
--                           se suman acá.
--
-- Relación en el modelo de Power BI: vw_bi_lineas 1 ──< N vw_bi_conceptos_pagados
-- por `linea_id`.
--
-- Notas de dominio:
--   · `importe` es el snapshot al momento del pago (cantidad × precio
--     congelados) — NUNCA joinear concepto_liquidacion para valorizar: el
--     maestro es mutable y mentiría sobre lo ya pagado.
--   · `tancadas` viene contada ida y vuelta: para pasadas reales dividir /2
--     en la medida DAX (no acá — se expone el dato crudo, igual que el Excel).
--   · La quincena en curso sigue siendo editable por el liquidador: los
--     refresh de Power BI pueden ver cambios hasta que termine la revisión.
--
-- El backend no gestiona vistas (create_all solo crea tablas): este archivo
-- es la única fuente de estas vistas. DIFERIBLE — no afecta a la aplicación;
-- solo lo necesita el usuario de reporting.
--
-- Permisos sugeridos (el usuario ya existe):
--   GRANT SELECT ON db_propia.vw_bi_lineas            TO 'powerbi_ro'@'%';
--   GRANT SELECT ON db_propia.vw_bi_conceptos_pagados TO 'powerbi_ro'@'%';
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW vw_bi_lineas AS
SELECT
    pl.id                  AS linea_id,
    p.quincena,
    pl.empresa_asignada,
    pl.planilla,
    pl.fecha_tarea,
    pl.nombre_cliente,
    pl.nombre_finca,
    pl.nombre_tarea,
    pl.nombre_tractor,
    pl.implemento,
    pl.legajo_asignado,
    pl.nombre_empleado,
    pl.cuit,
    pl.nombre_supervisor,
    pl.nombre_capataz,
    pl.grupo_pago_aplicado,
    pl.hsjornal,
    pl.hsmaquina,
    pl.tancadas,
    pl.unidades,
    pl.cantidad,
    pl.importe_total,
    pl.es_duplicado,
    pl.linea_incompleta,
    pl.alerta_legajo,
    pl.alerta_empresa
FROM preliquidacion p
JOIN preliquidacion_linea pl ON pl.preliquidacion_id = p.id;


CREATE OR REPLACE VIEW vw_bi_conceptos_pagados AS
SELECT
    ca.id                  AS concepto_pagado_id,
    ca.linea_id,
    ca.codigo_concepto,
    ca.descripcion,
    ca.tipo,
    ca.unidad_base,
    ca.cantidad,
    ca.precio,
    ca.importe,
    (ca.concepto_liquidacion_id IS NULL) AS es_concepto_manual,
    ca.fecha               AS fecha_aplicacion
FROM concepto_adicional ca;
