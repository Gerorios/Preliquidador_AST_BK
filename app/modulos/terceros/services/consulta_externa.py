"""SQL crudo con text() y parámetros sobre las bases externas, solo lectura.

Etapa 1 del plan (docs/modulos/terceros/plan-terceros.md): las consultas que
hoy alimentan las hojas de aterrizaje del Excel, traídas al módulo y acotadas
a una Quincena en vez de a "el año en curso".

Dos orígenes:
  - Sistema de campo (get_db_externa): viajes, cargas de combustible y horas de
    servicio de la maquinaria de terceros.
  - Sistema de compras / La Falda (get_db_sueldos): repuestos y reparaciones.

Las horas de taller no salen de una base sino del Google Sheet de la app del
taller: están en consulta_taller.py.

Punto de partida: las consultas originales, en docs/modulos/terceros/fuentes/.
Se conservan tal cual (mismos JOIN, mismos filtros de estado) para que la
etapa 1 pueda validarse contra el Excel; el único cambio es el rango de fechas
parametrizado. Cada corrección que cambie números va documentada abajo.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.quincena import calcular_rango_quincena


# La notación de quincena del Excel de origen: '08-1Q' = 1ra de agosto.
# Se devuelve como columna porque es el término del dominio (ver
# CONTEXT-terceros.md, "Quincena") y la clave con la que se compara contra
# las hojas del Excel.
QUINCENA_MES_EXPR = """CONCAT(LPAD(MONTH({campo}), 2, '0'), '-',
           IF(DAY({campo}) <= 15, 1, 2), 'Q')"""


QUERY_VIAJES = text(f"""
SELECT
    DATE_FORMAT(cregistros.date_time, '%Y-%m-%d') AS fecha_carga,
    DATE_FORMAT(pdcosechas.fecha, '%Y-%m-%d') AS fecha_uso,
    {QUINCENA_MES_EXPR.format(campo='pdcosechas.fecha')} AS quincena_mes,
    colectivos.nombre AS colectivo_nombre,
    colectivos.patente AS colectivo_patente,
    TRIM(SUBSTRING_INDEX(colectivos.descripcion, ';', 1)) AS colectivo_propiedad,
    clientes.nombre AS cliente,
    fincas.nombre AS finca,
    tareas.nombre AS nombre_tarea,
    usuarios_supervisor.name AS nombre_supervisor,
    usuarios_capataz.name AS nombre_capataz,
    usuarios_chofer.name AS nombre_chofer,
    CAST(cregistros.cantidadviajes AS DECIMAL(12,2)) AS cantidadviajes,
    cregistros.cantpersonas
FROM laa_pdcosechasregistros cregistros
    LEFT JOIN laa_colectivos colectivos ON colectivos.id = cregistros.colectivo
    LEFT JOIN laa_pdcosechas pdcosechas ON pdcosechas.id = cregistros.parent_id
    LEFT JOIN laa_supervisores supervisores ON supervisores.idusuario = pdcosechas.supervisor
    LEFT JOIN ast_users usuarios_supervisor ON usuarios_supervisor.id = supervisores.idusuario
    LEFT JOIN laa_clientes clientes ON clientes.id = pdcosechas.cliente
    LEFT JOIN laa_fincas fincas ON fincas.id = pdcosechas.finca
    LEFT JOIN laa_tareas tareas ON tareas.id = pdcosechas.tarea
    LEFT JOIN laa_legajos legajos_capataz ON legajos_capataz.id = cregistros.idlegajo
    LEFT JOIN ast_users usuarios_capataz ON usuarios_capataz.id = legajos_capataz.user
    LEFT JOIN laa_legajos legajos_chofer ON legajos_chofer.id = cregistros.chofer
    LEFT JOIN ast_users usuarios_chofer ON usuarios_chofer.id = legajos_chofer.user
WHERE cregistros.estado <> 9
    AND pdcosechas.estado <> 9
    AND DATE(pdcosechas.fecha) BETWEEN :fecha_desde AND :fecha_hasta
    AND UPPER(TRIM(colectivos.nombre)) NOT LIKE 'SIN COLECTIVO%%'
ORDER BY pdcosechas.fecha, colectivos.patente
""")


QUERY_CARGAS_COMBUSTIBLE = text(f"""
SELECT
    DATE_FORMAT(cfluidos.date_time, '%Y-%m-%d') AS fecha_carga,
    DATE_FORMAT(cfluidos.fecha, '%Y-%m-%d') AS fecha_uso,
    {QUINCENA_MES_EXPR.format(campo='cfluidos.fecha')} AS quincena_mes,
    colectivos.nombre AS colectivo_nombre,
    colectivos.patente AS colectivo_patente,
    TRIM(SUBSTRING_INDEX(colectivos.descripcion, ';', 1)) AS colectivo_propiedad,
    cfluidos.cantidad AS litros_cargados,
    cfluidos.numorden AS vale,
    origen.nombre AS origen_combustible,
    usuarios.name AS usuario_carga
FROM laa_controlfluidosoperativos cfluidos
    -- INNER JOIN, no LEFT: sin colectivo no hay tercero a quien descontarle
    INNER JOIN laa_colectivos colectivos ON colectivos.id = cfluidos.colectivo
    -- LEFT JOIN: si un registro no tuviera usuario, igual se lista
    LEFT JOIN ast_users usuarios ON usuarios.id = cfluidos.user
    -- de dónde salió el combustible: estación de servicio, depósito o supervisor
    LEFT JOIN laa_combustiblesorigen origen ON origen.id = cfluidos.proveedor
WHERE cfluidos.colectivo IS NOT NULL
    AND DATE(cfluidos.fecha) BETWEEN :fecha_desde AND :fecha_hasta
ORDER BY colectivos.patente, cfluidos.fecha
""")


# La consulta de repuestos se conserva tal como está hoy en el sistema de
# compras, con las tres correcciones que ya traía documentadas en el original
# (ver docs/modulos/terceros/fuentes/):
#   - El importe de una REPARACIÓN sale de detalle_importe, no de
#     cantcargas * precargas (que en esa rama viene en 0).
#   - La cantidad es la DESCARGADA a la máquina (movdet.ingreso), no la
#     comprada en la factura (que multiplicaba el gasto hasta por 25).
#   - El precio unitario sale de un as-of join: la última factura del insumo
#     anterior o igual a la fecha de descarga (ROW_NUMBER + rn_factura = 1).
#     Sin eso el 90% de las líneas de 2026 tenía precio indeterminado.
#
# PENDIENTE (plan-terceros.md, sección 3): la fecha con la que se imputa una
# línea debería ser la de la DESCARGA a la maquinaria, no la del encabezado
# del movimiento. Esta consulta filtra por la del encabezado —movim.fecha—
# porque es lo que hace el Excel y la etapa 1 se valida contra él. La fecha
# correcta viaja como fecha_descarga (movdet.fechamovim) para poder medir el
# desvío; el cambio de filtro se hace en la quincena de corte, no antes,
# porque mueve líneas de quincena y hasta de año.
QUERY_REPUESTOS = text(f"""
SELECT
    ru.id_maquina,
    ru.maquina,
    ru.fecha,
    ru.fecha_descarga,
    {QUINCENA_MES_EXPR.format(campo='ru.fecha')} AS quincena_mes,
    ru.tipo_insumo,
    ru.rubro,
    ru.repuesto,
    ru.ingreso        AS cantidad,          -- descargado a la máquina (movdet.ingreso)
    ru.precargas,
    CASE WHEN ru.reparacion = 'S' THEN ru.detalle_importe
         ELSE ru.ingreso * ru.precargas END AS monto_total,
    ru.reparacion,
    ru.nombreprove,
    grp1.grupo1_nombre AS propiedad_maquina
FROM (
    -- ===================== INSUMOS =====================
    SELECT
        Base.id_maquina, Base.maquina, Base.tipo, Base.idmovdet,
        Base.fecha, Base.fecha_descarga,
        Base.usuario, Base.solicitante, Base.idsolicitantes,
        Base.id_insumo, Base.tipo_insumo, Base.rubro, Base.subrubro,
        Base.grupo3, Base.insumosstock_cod, Base.ingreso, Base.repuesto,
        Base.cantcargas, Base.exsnuecargas, Base.precargas,
        Base.fechfaccargas, Base.numero,
        ' ' AS detalle_repara,
        0 AS detalle_importe,
        '' AS reparacion,
        Base.origen, Base.destino, Base.id_proveedor, Base.nombreprove
    FROM (
        SELECT * FROM (
        SELECT
            Tmp_descarga.id_maquina, Tmp_descarga.maquina, Tmp_descarga.tipo,
            Tmp_descarga.idmovdet, Tmp_descarga.fecha, Tmp_descarga.fecha_descarga,
            Tmp_descarga.usuario, Tmp_descarga.solicitante, Tmp_descarga.idsolicitantes,
            Tmp_descarga.id_insumo, Tmp_descarga.tipo_insumo, Tmp_descarga.rubro,
            Tmp_descarga.subrubro, Tmp_descarga.grupo3, Tmp_descarga.insumosstock_cod,
            Tmp_descarga.ingreso, Tmp_descarga.repuesto, Tmp_descarga.numero,
            Tmp_cargas.cantcargas, Tmp_cargas.exsnuecargas, Tmp_cargas.precargas,
            Tmp_cargas.fechfaccargas, Tmp_descarga.origen, Tmp_descarga.destino,
            Tmp_cargas.id_proveedor, Tmp_cargas.nombreprove,
            ROW_NUMBER() OVER (
                PARTITION BY Tmp_descarga.idmovdet, Tmp_descarga.id_insumo
                ORDER BY Tmp_cargas.fechfaccargas DESC, Tmp_cargas.fact_id DESC
            ) AS rn_factura
        FROM (
            SELECT
                pp.id_maquina,
                qq.nombre AS maquina,
                rr.tipo_nomcorto AS tipo,
                idmovdet,
                xx.fecha,                          -- encabezado del movimiento (movim)
                pp.fechamovim AS fecha_descarga,   -- descarga a la maquinaria (movdet)
                pp.usuario,
                CASE WHEN ISNULL(ss.apellido) THEN ' '
                     ELSE CONCAT(TRIM(ss.apellido), ', ', TRIM(ss.nombre)) END AS solicitante,
                ss.idsolicitantes,
                uu.idcodigo AS id_insumo,
                b.tipo_nomcorto AS tipo_insumo,
                g1.grupo1_nomcorto AS rubro,
                g2.grupo2_nomcorto AS subrubro,
                g3.grupo3_nomcorto AS grupo3,
                uu.cod AS insumosstock_cod,
                pp.ingreso AS ingreso,
                uu.nombre AS repuesto,
                pp.numero,
                jj.nombredepositos AS origen,
                hh.nombre AS destino
            FROM movdet AS pp
            LEFT JOIN movim AS xx ON pp.numero = xx.numero
            LEFT JOIN nuemaquinas AS qq ON pp.id_maquina = qq.id_maquina
            LEFT JOIN nuetipomaquinas AS rr ON qq.tipo_id = rr.tipo_id
            LEFT JOIN nuesolicitantes AS ss ON pp.codsolimpu = ss.idsolicitantes
            LEFT JOIN nueinterdepositocantidad AS tt ON pp.idnueinter = tt.idnueinter
            LEFT JOIN nueinsumosstock AS uu ON tt.idcodigo = uu.idcodigo
            LEFT JOIN nuetipoinsumos AS b ON uu.tipo_id = b.tipo_id
            LEFT JOIN nuegrupo1insumos AS g1 ON uu.grupo1_id = g1.grupo1_id
            LEFT JOIN nuegrupo2insumos AS g2 ON uu.grupo2_id = g2.grupo2_id
            LEFT JOIN nuegrupo3insumos AS g3 ON uu.grupo3_id = g3.grupo3_id
            LEFT JOIN nuecampos AS hh ON pp.coddes = hh.id_campo
            LEFT JOIN nuedepositos AS jj ON xx.depoactual = jj.id_depositos
            WHERE xx.borrado <> 'S' AND pp.borrado <> 'S'
              AND (xx.deposito = 4 OR xx.deposito = 0)
        ) AS Tmp_descarga
        LEFT JOIN (
            SELECT
                aa.fact_id,  -- desempata dos facturas del mismo día
                cod AS insucargas, factde_cantidad AS cantcargas,
                dd.cantidad AS exsnuecargas,
                CASE WHEN factde_descuento > 0 THEN factde_neto - factde_descuento
                     ELSE factde_neto END AS precargas,
                fact_fechafact AS fechfaccargas, ee.id_proveedor,
                ee.nombre AS nombreprove
            FROM factmovim AS aa
            LEFT JOIN factdetalle AS bb ON aa.fact_id = bb.fact_id
            LEFT JOIN nueinterdepositocantidad AS cc ON bb.idcodigo = cc.idnueinter
            LEFT JOIN nueinsumosstock AS dd ON cc.idcodigo = dd.idcodigo
            LEFT JOIN nueproveedores AS ee ON aa.fact_idproveedor = ee.id_proveedor
            WHERE bb.borrado <> 'S' AND factde_neto > 0
        ) AS Tmp_cargas
        ON TRIM(Tmp_descarga.insumosstock_cod) = TRIM(Tmp_cargas.insucargas)
        AND Tmp_descarga.fecha >= Tmp_cargas.fechfaccargas
        ) AS Ranked
        WHERE rn_factura = 1   -- la factura vigente al momento de la descarga
    ) AS Base

    UNION ALL

    -- =================== REPARACIONES ===================
    -- No hay descarga a la maquinaria: la fecha es la de la factura de la
    -- reparacion, asi que fecha y fecha_descarga son la misma.
    SELECT
        g.id_maquina,
        g.nombre AS maquina,
        k.tipo_nomcorto AS tipo,
        1 AS idmovdet,
        j.fact_fechafact AS fecha,
        j.fact_fechafact AS fecha_descarga,
        e.factde_usuario AS usuario,
        '' AS solicitante,
        0 AS idsolicitantes,
        i.idcodigo AS id_insumo,
        b.tipo_nomcorto AS tipo_insumo,
        g1.grupo1_nomcorto AS rubro,
        g2.grupo2_nomcorto AS subrubro,
        g3.grupo3_nomcorto AS grupo3,
        i.cod AS insumosstock_cod,
        f.factde_cantidad AS ingreso,
        i.nombre AS repuesto,
        0 AS cantcargas,
        0 AS exsnuecargas,
        f.factde_neto AS precargas,
        j.fact_fechafact AS fechfaccargas,
        '00000000' AS numero,
        e.factdere_des AS detalle_repara,
        e.importe AS detalle_importe,
        'S' AS reparacion,
        ' ' AS origen,
        ' ' AS destino,
        l.id_proveedor,
        l.nombre AS nombreprove
    FROM factdetrepa AS e
    LEFT JOIN factdetalle AS f ON e.factde_id = f.factde_id AND e.fact_id = f.fact_id
    LEFT JOIN nuemaquinas AS g ON f.id_maquina = g.id_maquina
    LEFT JOIN nueinterdepositocantidad AS h ON f.idcodigo = h.idnueinter
    LEFT JOIN nueinsumosstock AS i ON h.idcodigo = i.idcodigo
    LEFT JOIN nuetipoinsumos AS b ON i.tipo_id = b.tipo_id
    LEFT JOIN nuegrupo1insumos AS g1 ON i.grupo1_id = g1.grupo1_id
    LEFT JOIN nuegrupo2insumos AS g2 ON i.grupo2_id = g2.grupo2_id
    LEFT JOIN nuegrupo3insumos AS g3 ON i.grupo3_id = g3.grupo3_id
    LEFT JOIN factmovim AS j ON e.fact_id = j.fact_id
    LEFT JOIN nuetipomaquinas AS k ON g.tipo_id = k.tipo_id
    LEFT JOIN nueproveedores AS l ON j.fact_idproveedor = l.id_proveedor
    WHERE f.borrado <> 'S' AND e.borrado <> 'S' AND g.id_maquina <> 0
) AS ru
LEFT JOIN nuemaquinas AS maq ON ru.id_maquina = maq.id_maquina
LEFT JOIN nuegrupo1maquinas AS grp1 ON maq.grupo1_id = grp1.grupo1_id
WHERE UPPER(TRIM(grp1.grupo1_nombre)) LIKE '%%TERCERO%%'
    AND ru.fecha BETWEEN :fecha_desde AND :fecha_hasta
ORDER BY ru.fecha, ru.maquina
""")



# ─── Horas de servicio (etapa 4) ────────────────────────────────────────────
# La maquinaria del Tercero trabajando en las fincas. Es lo que se le PAGA por
# el servicio de maquinaria — no confundir con la Hora de reparación, que es el
# taller arreglándole la máquina y va con el signo contrario.
#
# La escribió el usuario contra Chinagro y se trae tal cual; lo único que se
# cambió es el rango de fechas, que venía fijo en 2026.
#
# Las horas se registran en tres partes diarias distintas y cada una las guarda
# en otro lugar, por eso el UNION de cuatro ramas:
#   COSECHA      la máquina está en el detalle, la tarea en la cabecera
#   MAQUINARIA   la tarea está en cada registro, no en la cabecera
#   PULVERIZADA  cada registro lleva dos tractores, cada uno con sus horas; el
#                turbo y la nodriza no tienen horas propias, así que no suman
#
# Las seis columnas de horas son varchar, vienen con espacios y hay registros
# con texto adentro ('.50', '11playas muy lejo'). Por eso cada una se valida con
# REGEXP antes de convertir, en vez de dejar que MySQL la tome como cero.
#
# `unidades` es cuánto midió la tarea y `unidad` de qué son: BINS, TANCADAS,
# HORAS, HORAS TRACTOR o JORNAL. Sólo la planilla de MAQUINARIA las carga; en
# cosecha y pulverizadas vienen vacías. Ojo con sumarlas sin mirar `unidad`:
# mezclaría bins con tancadas y con horas. `unidad` es lo que la tarea mide,
# **no** cómo se paga — eso lo decide la Unidad base de la tarifa, igual que el
# Grupo de pago de Preliquidación (ver CONTEXT.md).
#
# El dueño sale del último campo de `descripcion`, que tiene la forma
# PROPIEDAD;TIPO;MARCA;MODELO;NUMERO;DUEÑO. Cuando ese campo trae una patente en
# vez de un nombre se devuelve NULL, para que el hueco se vea en lugar de
# liquidarle las horas a una patente. En las máquinas con horas de 2026 está
# cargado en todas.
QUERY_HORAS_SERVICIO = text(f"""
SELECT
    DATE(h.fecha) AS fecha,
    {QUINCENA_MES_EXPR.format(campo='h.fecha')} AS quincena_mes,
    h.planilla,
    clientes.nombre    AS cliente,
    fincas.nombre      AS finca,
    tareas.nombre      AS tarea,
    maquinarias.nombre AS maquinaria,
    NULLIF(
        TRIM(REPLACE(REPLACE(
            CASE
                -- si el último campo es una patente, no es el dueño
                WHEN TRIM(SUBSTRING_INDEX(maquinarias.descripcion, ';', -1))
                     REGEXP '^([A-Z]{{3}}[0-9]{{3}}|[A-Z]{{2}}[0-9]{{3}}[A-Z]{{2}})$' THEN ''
                ELSE TRIM(SUBSTRING_INDEX(maquinarias.descripcion, ';', -1))
            END, ',', ' '), '  ', ' ')
    ), '')             AS tercero,
    usuarios_supervisor.`name` AS supervisor,
    h.hsmaquina        AS horas_maquina,
    h.unidades         AS unidades,
    tareas.unidad      AS unidad
FROM (
    -- 1. Parte diario de COSECHA
    SELECT
        'COSECHA'      AS planilla,
        pdc.fecha      AS fecha,
        pdc.cliente    AS cliente,
        pdc.finca      AS finca,
        pdc.tarea      AS tarea,
        pdc.supervisor AS supervisor,
        r1.maquinaria  AS maquinaria,
        CASE WHEN TRIM(r1.hsmaquina) REGEXP '^[0-9]*[.]?[0-9]+$'
             THEN CAST(TRIM(r1.hsmaquina) AS DECIMAL(10,2)) ELSE 0 END AS hsmaquina,
        NULL AS unidades
    FROM laa_pdcosechasregistros1 r1
        INNER JOIN laa_pdcosechas pdc ON pdc.id = r1.parent_id
    WHERE r1.estado <> 9 AND pdc.estado <> 9

    UNION ALL

    -- 2. Parte diario de MAQUINARIA
    SELECT
        'MAQUINARIA', pdm.fecha, pdm.cliente, pdm.finca, mr.tarea,
        pdm.supervisor, mr.maquinaria,
        CASE WHEN TRIM(mr.hsmaquina) REGEXP '^[0-9]*[.]?[0-9]+$'
             THEN CAST(TRIM(mr.hsmaquina) AS DECIMAL(10,2)) ELSE 0 END,
        CASE WHEN TRIM(mr.unidades)  REGEXP '^[0-9]*[.]?[0-9]+$'
             THEN CAST(TRIM(mr.unidades)  AS DECIMAL(12,2)) ELSE NULL END
    FROM laa_pdmaquinariasregistros mr
        INNER JOIN laa_pdmaquinarias pdm ON pdm.id = mr.parent_id
    WHERE mr.estado <> 9 AND pdm.estado <> 9

    UNION ALL

    -- 3. PULVERIZADAS, tractor 1
    SELECT
        'PULVERIZADA', pdp.fecha, pdp.cliente, pdp.finca, pdp.tarea,
        pdp.supervisor, pr.tractor1,
        CASE WHEN TRIM(pr.hsmaquina1) REGEXP '^[0-9]*[.]?[0-9]+$'
             THEN CAST(TRIM(pr.hsmaquina1) AS DECIMAL(10,2)) ELSE 0 END,
        NULL
    FROM laa_pdpulverizadasregistros pr
        INNER JOIN laa_pdpulverizadas pdp ON pdp.id = pr.parent_id
    WHERE pr.estado <> 9 AND pdp.estado <> 9 AND pr.tractor1 IS NOT NULL

    UNION ALL

    -- 4. PULVERIZADAS, tractor 2
    SELECT
        'PULVERIZADA', pdp.fecha, pdp.cliente, pdp.finca, pdp.tarea,
        pdp.supervisor, pr.tractor2,
        CASE WHEN TRIM(pr.hsmaquina2) REGEXP '^[0-9]*[.]?[0-9]+$'
             THEN CAST(TRIM(pr.hsmaquina2) AS DECIMAL(10,2)) ELSE 0 END,
        NULL
    FROM laa_pdpulverizadasregistros pr
        INNER JOIN laa_pdpulverizadas pdp ON pdp.id = pr.parent_id
    WHERE pr.estado <> 9 AND pdp.estado <> 9 AND pr.tractor2 IS NOT NULL
) h
    INNER JOIN laa_maquinarias maquinarias ON maquinarias.id = h.maquinaria
    LEFT JOIN laa_clientes clientes ON clientes.id = h.cliente
    LEFT JOIN laa_fincas fincas     ON fincas.id = h.finca
    LEFT JOIN laa_tareas tareas     ON tareas.id = h.tarea
    LEFT JOIN laa_supervisores supervisores ON supervisores.idusuario = h.supervisor
    LEFT JOIN ast_users usuarios_supervisor ON usuarios_supervisor.id = supervisores.idusuario
-- 'TERCERO' en singular existe en una máquina; dejarla afuera sería perderle las horas.
WHERE TRIM(SUBSTRING_INDEX(maquinarias.descripcion, ';', 1)) IN ('TERCEROS', 'TERCERO')
  -- DATE(): la fecha viene como datetime con hora 03:00, y sin esto el
  -- último día de la quincena queda afuera entero.
  AND DATE(h.fecha) BETWEEN :fecha_desde AND :fecha_hasta
  -- Sin horas de máquina ni cantidad no hay nada sobre qué aplicar una tarifa,
  -- así que la fila no es una línea a liquidar. En 2026 son 16 filas con horas
  -- de jornal y nada más (86 horas): candidatas a una Verificación, no a pago.
  AND (h.hsmaquina > 0 OR h.unidades > 0)
ORDER BY h.fecha, maquinarias.nombre
""")


# ─── Maestros, para las Alertas de cruce (etapa 3) ──────────────────────────
# No alimentan ninguna liquidación: sirven para comparar los tres sistemas
# entre sí y avisar dónde no se encuentran. Ver services/alertas_cruce.py.

QUERY_MAQUINARIAS_TERCEROS = text("""
SELECT id,
       nombre,
       descripcion,
       TRIM(SUBSTRING_INDEX(descripcion, ';', 1)) AS propiedad
FROM laa_maquinarias
WHERE estado <> 9
  AND UPPER(TRIM(SUBSTRING_INDEX(descripcion, ';', 1))) LIKE '%%TERCERO%%'
ORDER BY nombre
""")

# Todos los colectivos, no sólo los de terceros: dos de las alertas son
# justamente sobre los que tienen la propiedad mal escrita o vacía, que por
# definición no se pueden filtrar por propiedad.
QUERY_COLECTIVOS = text("""
SELECT id,
       nombre,
       patente,
       descripcion,
       TRIM(SUBSTRING_INDEX(descripcion, ';', 1))  AS propiedad,
       TRIM(SUBSTRING_INDEX(descripcion, ';', -1)) AS patente_descripcion
FROM laa_colectivos
WHERE estado <> 9
ORDER BY nombre
""")

QUERY_MAQUINAS_TERCEROS_COMPRAS = text("""
SELECT m.id_maquina,
       m.nombre,
       m.codigo,
       g.grupo1_nombre AS propiedad
FROM nuemaquinas m
LEFT JOIN nuegrupo1maquinas g ON m.grupo1_id = g.grupo1_id
WHERE UPPER(TRIM(g.grupo1_nombre)) LIKE '%%TERCERO%%'
ORDER BY m.nombre
""")

# Cuántas líneas de descarga tuvo cada máquina en el año. Es lo que separa una
# alerta accionable de una fila muerta: sin movimiento no hay nada que
# reclamarle a nadie todavía.
QUERY_LINEAS_POR_MAQUINA = text("""
SELECT pp.id_maquina, COUNT(*) AS lineas
FROM movdet pp
LEFT JOIN movim xx ON pp.numero = xx.numero
WHERE pp.borrado <> 'S'
  AND xx.borrado <> 'S'
  AND (xx.deposito = 4 OR xx.deposito = 0)
  AND YEAR(xx.fecha) = :anio
GROUP BY pp.id_maquina
""")

# ─── Padrón de bienes de terceros (etapa 6) ─────────────────────────────────
#
# Todo lo que un Tercero tiene y la empresa le asegura: sus colectivos y su
# maquinaria. Sirve para que quien carga los seguros elija de una lista en vez
# de tipear el nombre — si lo tipea, tiene que coincidir exacto con el del
# sistema de campo o el seguro no se le imputa a nadie.
#
# Sale del sistema de campo, que es el maestro. Dos orígenes distintos:
#   colectivos   el `nombre` ES el del dueño y la patente está en su columna
#   choferes     no hay padrón: se deducen de quién manejó sus colectivos
#   maquinaria   el dueño es el último campo de `descripcion`… salvo en los
#                vehículos, donde ese último campo es la patente. Cuando pasa
#                eso el dueño vuelve vacío y se ve el hueco, en vez de dar por
#                dueño a una patente.
QUERY_BIENES_TERCEROS = text("""
SELECT * FROM (
    SELECT
        'colectivo'                 AS origen,
        c.id                        AS id_origen,
        TRIM(c.nombre)              AS tercero,
        TRIM(c.nombre)              AS nombre,
        NULLIF(TRIM(c.patente), '') AS patente,
        NULLIF(TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(c.descripcion, ';', 4), ';', -1)), '') AS detalle
    FROM laa_colectivos c
    WHERE c.estado <> 9
      AND UPPER(TRIM(SUBSTRING_INDEX(c.descripcion, ';', 1))) LIKE '%%TERCERO%%'
      AND UPPER(TRIM(c.nombre)) NOT LIKE 'SIN COLECTIVO%%'

    UNION ALL

    SELECT
        'maquinaria',
        m.id,
        -- El último campo es el dueño, salvo cuando es una patente.
        NULLIF(
            CASE WHEN TRIM(SUBSTRING_INDEX(m.descripcion, ';', -1))
                      REGEXP '^([A-Z]{3}[0-9]{3}|[A-Z]{2}[0-9]{3}[A-Z]{2}|[A-Z][0-9]{3}[A-Z]{3})$'
                 THEN ''
                 ELSE TRIM(REPLACE(SUBSTRING_INDEX(m.descripcion, ';', -1), ',', ' '))
            END, ''),
        TRIM(m.nombre),
        -- La patente puede estar en el último campo o embebida en el nombre.
        NULLIF(
            CASE WHEN TRIM(SUBSTRING_INDEX(m.descripcion, ';', -1))
                      REGEXP '^([A-Z]{3}[0-9]{3}|[A-Z]{2}[0-9]{3}[A-Z]{2}|[A-Z][0-9]{3}[A-Z]{3})$'
                 THEN TRIM(SUBSTRING_INDEX(m.descripcion, ';', -1))
                 ELSE ''
            END, ''),
        NULLIF(TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(m.descripcion, ';', 2), ';', -1)), '')
    FROM laa_maquinarias m
    WHERE m.estado <> 9
      AND UPPER(TRIM(SUBSTRING_INDEX(m.descripcion, ';', 1))) LIKE '%%TERCERO%%'

    UNION ALL

    -- Los choferes de cada tercero. No hay un padrón de choferes por dueño en
    -- ningún lado: se deducen de quién manejó sus colectivos. Por eso llevan
    -- ventana de un año — un chofer que no maneja hace dos años no es suyo.
    SELECT DISTINCT
        'chofer',
        u.id,
        TRIM(col.nombre),
        TRIM(u.name),
        NULLIF(TRIM(u.username), ''),   -- el CUIL
        'CHOFER'
    FROM laa_pdcosechasregistros r
    JOIN laa_pdcosechas p ON p.id = r.parent_id
    JOIN laa_colectivos col ON col.id = r.colectivo
    JOIN laa_legajos l ON l.id = r.chofer
    JOIN ast_users u ON u.id = l.user
    WHERE r.estado <> 9 AND p.estado <> 9
      AND p.fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
      AND UPPER(TRIM(SUBSTRING_INDEX(col.descripcion, ';', 1))) LIKE '%%TERCERO%%'
      AND UPPER(TRIM(col.nombre)) NOT LIKE 'SIN COLECTIVO%%'
      AND u.name IS NOT NULL
) b
ORDER BY (b.tercero IS NULL), b.tercero, b.origen, b.nombre
""")


# Las columnas que devuelve cada consulta. Están acá y no solo en el SQL porque
# son el contrato de la etapa 1: son las mismas que hoy tienen las hojas de
# aterrizaje del Excel, y los tests las fijan para que un cambio en el SELECT
# no pase inadvertido.
COLUMNAS_VIAJES = (
    "fecha_carga", "fecha_uso", "quincena_mes", "colectivo_nombre",
    "colectivo_patente", "colectivo_propiedad", "cliente", "finca",
    "nombre_tarea", "nombre_supervisor", "nombre_capataz", "nombre_chofer",
    "cantidadviajes", "cantpersonas",
)
COLUMNAS_CARGAS_COMBUSTIBLE = (
    "fecha_carga", "fecha_uso", "quincena_mes", "colectivo_nombre",
    "colectivo_patente", "colectivo_propiedad", "litros_cargados", "vale",
    "origen_combustible", "usuario_carga",
)
COLUMNAS_HORAS_SERVICIO = (
    "fecha", "quincena_mes", "planilla", "cliente", "finca", "tarea",
    "maquinaria", "tercero", "supervisor", "horas_maquina", "unidades", "unidad",
)
COLUMNAS_REPUESTOS = (
    "id_maquina", "maquina", "fecha", "fecha_descarga", "quincena_mes",
    "tipo_insumo", "rubro", "repuesto", "cantidad", "precargas",
    "monto_total", "reparacion", "nombreprove", "propiedad_maquina",
)


class ConsultaExternaService:
    """Las tres consultas de la quincena que salen de una base.

    Dos orígenes distintos, una sola puerta: el que llama pide "los viajes de
    esta quincena" y no se ocupa de en qué base viven. Las horas de taller son
    la cuarta consulta y están en consulta_taller.py, porque no salen de una
    base sino del Sheet de la app del taller.
    """

    def __init__(self, db_externa: Session, db_sueldos: Session):
        self.db_externa = db_externa      # sistema de campo
        self.db_sueldos = db_sueldos      # sistema de compras (La Falda)

    def viajes(self, quincena: date) -> list[dict]:
        return self._traer(self.db_externa, QUERY_VIAJES, quincena)

    def cargas_combustible(self, quincena: date) -> list[dict]:
        return self._traer(self.db_externa, QUERY_CARGAS_COMBUSTIBLE, quincena)

    def repuestos(self, quincena: date) -> list[dict]:
        return self._traer(self.db_sueldos, QUERY_REPUESTOS, quincena)

    def horas_servicio(self, quincena: date) -> list[dict]:
        """Lo que la maquinaria del Tercero trabajó en las fincas.

        Trae la hora de máquina y la cantidad que midió la tarea: sobre cuál de
        las dos se paga decide la Unidad base de la tarifa, no el dato."""
        return self._traer(self.db_externa, QUERY_HORAS_SERVICIO, quincena)

    @staticmethod
    def _traer(db: Session, query, quincena: date) -> list[dict]:
        fecha_desde, fecha_hasta = calcular_rango_quincena(quincena)
        resultado = db.execute(
            query, {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta}
        )
        columnas = list(resultado.keys())
        return [dict(zip(columnas, fila)) for fila in resultado.fetchall()]

    # ─── Maestros, para las Alertas de cruce ────────────────────────────────

    def maquinarias_terceros_campo(self) -> list[dict]:
        return self._sin_parametros(self.db_externa, QUERY_MAQUINARIAS_TERCEROS)

    def colectivos_campo(self) -> list[dict]:
        return self._sin_parametros(self.db_externa, QUERY_COLECTIVOS)

    def maquinas_terceros_compras(self) -> list[dict]:
        return self._sin_parametros(self.db_sueldos, QUERY_MAQUINAS_TERCEROS_COMPRAS)

    def bienes_terceros(self) -> list[dict]:
        """Colectivos, maquinaria y choferes de terceros: lo que se asegura."""
        return self._sin_parametros(self.db_externa, QUERY_BIENES_TERCEROS)

    def lineas_por_maquina(self, anio: int) -> dict[int, int]:
        """Cuántas líneas de repuestos tuvo cada máquina en el año."""
        resultado = self.db_sueldos.execute(QUERY_LINEAS_POR_MAQUINA, {"anio": anio})
        return {fila[0]: fila[1] for fila in resultado.fetchall() if fila[0] is not None}

    @staticmethod
    def _sin_parametros(db: Session, query) -> list[dict]:
        resultado = db.execute(query)
        columnas = list(resultado.keys())
        return [dict(zip(columnas, fila)) for fila in resultado.fetchall()]
