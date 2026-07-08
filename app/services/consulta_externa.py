"""
Servicio de consulta a la BD externa (solo lectura).
"""
from datetime import date
import calendar
from sqlalchemy.orm import Session
from sqlalchemy import text
import time


def calcular_rango_quincena(quincena: date) -> tuple[date, date]:
    if quincena.day == 1:
        return quincena, quincena.replace(day=15)
    else:
        ultimo_dia = calendar.monthrange(quincena.year, quincena.month)[1]
        return quincena.replace(day=16), quincena.replace(day=ultimo_dia)


# Expresión reutilizable para extraer el grupo_pago desde tareas.descripcion
# (segunda parte separada por ';', igual que en QUERY_TAREAS)
GRUPO_PAGO_EXPR = "TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(tareas.descripcion, ';', 2), ';', -1))"


QUERY_PRINCIPAL = text(f"""
SELECT *
FROM (
  SELECT 'PULVERIZADA' AS planilla,
         DATE_FORMAT(pdpulve.fecha, '%Y-%m-%d') AS fecha_tarea,
         CONCAT(
           CASE WHEN DAY(pdpulve.fecha) <= 15 THEN '1' ELSE '2' END,
           '/', DATE_FORMAT(pdpulve.fecha, '%b'), '/', DATE_FORMAT(pdpulve.fecha, '%Y')
         ) AS quincena,
         clientes.nombre AS nombre_cliente,
         fincas.nombre AS nombre_finca,
         tareas.nombre AS nombre_tarea,
         {GRUPO_PAGO_EXPR} AS grupo_pago,
         maquinarias_tractor1.nombre AS nombre_tractor,
         legajo1.legajo,
         usuario1.name AS nombre_empleado,
         usuario1.username AS cuit,
         supervisor.name AS nombre_supervisor,
         ' ' AS nombre_capataz,
         maquinarias_turbo.nombre AS implemento,
         pdpulve.unidades AS unidades,
         pregistros.trancadas1 AS tancadas,
         pregistros.hsjornal1 AS hsjornal,
         pregistros.hsmaquina1 AS hsmaquina
  FROM laa_pdpulverizadas pdpulve
  INNER JOIN laa_pdpulverizadasregistros pregistros ON pregistros.parent_id = pdpulve.id AND pregistros.estado <> 9
  LEFT JOIN laa_maquinarias maquinarias_tractor1 ON maquinarias_tractor1.id = pregistros.tractor1
  LEFT JOIN laa_maquinarias maquinarias_turbo ON maquinarias_turbo.id = pregistros.turbo
  LEFT JOIN laa_maquinarias maquinarias_nodriza ON maquinarias_nodriza.id = pregistros.nodriza
  LEFT JOIN laa_clientes clientes ON clientes.id = pdpulve.cliente
  LEFT JOIN laa_fincas fincas ON fincas.id = pdpulve.finca
  LEFT JOIN laa_legajos legajo1 ON legajo1.id = pregistros.idlegajo1
  LEFT JOIN ast_users usuario1 ON usuario1.id = legajo1.user
  LEFT JOIN ast_users supervisor ON supervisor.id = pdpulve.supervisor
  LEFT JOIN laa_tareas tareas ON tareas.id = pdpulve.tarea
  WHERE pdpulve.estado <> 9
    AND DATE(pdpulve.fecha) BETWEEN :fecha_desde AND :fecha_hasta

  UNION ALL

  SELECT 'PULVERIZADA' AS planilla,
         DATE_FORMAT(pdpulve.fecha, '%Y-%m-%d') AS fecha_tarea,
         CONCAT(
           CASE WHEN DAY(pdpulve.fecha) <= 15 THEN '1' ELSE '2' END,
           '/', DATE_FORMAT(pdpulve.fecha, '%b'), '/', DATE_FORMAT(pdpulve.fecha, '%Y')
         ) AS quincena,
         clientes.nombre AS nombre_cliente,
         fincas.nombre AS nombre_finca,
         tareas.nombre AS nombre_tarea,
         {GRUPO_PAGO_EXPR} AS grupo_pago,
         maquinarias_tractor2.nombre AS nombre_tractor,
         legajo2.legajo,
         usuario2.name AS nombre_empleado,
         usuario2.username AS cuit,
         supervisor.name AS nombre_supervisor,
         ' ' AS nombre_capataz,
         maquinarias_nodriza.nombre AS implemento,
         pdpulve.unidades AS unidades,
         pregistros.trancadas2 AS tancadas,
         pregistros.hsjornal2 AS hsjornal,
         pregistros.hsmaquina2 AS hsmaquina
  FROM laa_pdpulverizadas pdpulve
  INNER JOIN laa_pdpulverizadasregistros pregistros ON pregistros.parent_id = pdpulve.id AND pregistros.estado <> 9
  LEFT JOIN laa_maquinarias maquinarias_tractor2 ON maquinarias_tractor2.id = pregistros.tractor2
  LEFT JOIN laa_maquinarias maquinarias_nodriza ON maquinarias_nodriza.id = pregistros.nodriza
  LEFT JOIN laa_clientes clientes ON clientes.id = pdpulve.cliente
  LEFT JOIN laa_fincas fincas ON fincas.id = pdpulve.finca
  LEFT JOIN laa_legajos legajo2 ON legajo2.id = pregistros.idlegajo2
  LEFT JOIN ast_users usuario2 ON usuario2.id = legajo2.user
  LEFT JOIN ast_users supervisor ON supervisor.id = pdpulve.supervisor
  LEFT JOIN laa_tareas tareas ON tareas.id = pdpulve.tarea
  WHERE pdpulve.estado <> 9
    AND DATE(pdpulve.fecha) BETWEEN :fecha_desde AND :fecha_hasta

  UNION ALL

  SELECT 'MAQUINARIA' AS planilla,
         DATE_FORMAT(pdmaquinarias.fecha, '%Y-%m-%d') AS fecha_tarea,
         CONCAT(
           CASE WHEN DAY(pdmaquinarias.fecha) <= 15 THEN '1' ELSE '2' END,
           '/', DATE_FORMAT(pdmaquinarias.fecha, '%b'), '/', DATE_FORMAT(pdmaquinarias.fecha, '%Y')
         ) AS quincena,
         clientes.nombre AS nombre_cliente,
         fincas.nombre AS nombre_finca,
         tareas.nombre AS nombre_tarea,
         {GRUPO_PAGO_EXPR} AS grupo_pago,
         maquinarias.nombre AS nombre_tractor,
         legajos_emple.legajo AS legajo,
         usuario_empleado.name AS nombre_empleado,
         usuario_empleado.username AS cuit,
         usuario_supervisor.name AS nombre_supervisor,
         ' ' AS nombre_capataz,
         implemento.nombre AS implemento,
         mregistros.unidades AS unidades,
         0 AS tancadas,
         mregistros.hsjornal AS hsjornal,
         mregistros.hsmaquina AS hsmaquina
  FROM laa_pdmaquinarias pdmaquinarias
  INNER JOIN laa_pdmaquinariasregistros mregistros ON mregistros.parent_id = pdmaquinarias.id AND mregistros.estado <> 9
  LEFT JOIN laa_clientes clientes ON pdmaquinarias.cliente = clientes.id
  LEFT JOIN laa_fincas fincas ON pdmaquinarias.finca = fincas.id
  LEFT JOIN laa_supervisores supervisores ON pdmaquinarias.supervisor = supervisores.idusuario
  LEFT JOIN ast_users usuario_supervisor ON supervisores.idusuario = usuario_supervisor.id
  LEFT JOIN laa_lubricantes lubricantes ON lubricantes.id = mregistros.lubricante
  LEFT JOIN laa_combustibles combustibles ON combustibles.id = mregistros.combustible
  LEFT JOIN laa_maquinarias maquinarias ON maquinarias.id = mregistros.maquinaria
  LEFT JOIN laa_maquinarias implemento ON implemento.id = mregistros.implemento
  LEFT JOIN laa_tareas tareas ON tareas.id = mregistros.tarea
  LEFT JOIN laa_legajos legajos_emple ON legajos_emple.id = mregistros.idlegajo
  LEFT JOIN ast_users usuario_empleado ON usuario_empleado.id = legajos_emple.user
  WHERE pdmaquinarias.estado <> 9
    AND DATE(pdmaquinarias.fecha) BETWEEN :fecha_desde AND :fecha_hasta

  UNION ALL

  SELECT 'TAREAMANUAL' AS planilla,
         DATE_FORMAT(pdtareas.fecha, '%Y-%m-%d') AS fecha_tarea,
         CONCAT(
           CASE WHEN DAY(pdtareas.fecha) <= 15 THEN '1' ELSE '2' END,
           '/', DATE_FORMAT(pdtareas.fecha, '%b'), '/', DATE_FORMAT(pdtareas.fecha, '%Y')
         ) AS quincena,
         clientes.nombre AS nombre_cliente,
         fincas.nombre AS nombre_finca,
         tareas.nombre AS nombre_tarea,
         {GRUPO_PAGO_EXPR} AS grupo_pago,
         ' ' AS nombre_tractor,
         legajo_manual.legajo AS legajo,
         usuario_empleado.name AS nombre_empleado,
         usuario_empleado.username AS cuit,
         usuario_supervisor.name AS nombre_supervisor,
         ' ' AS nombre_capataz,
         ' ' AS implemento,
         tregistros.unidades AS unidades,
         0 AS tancadas,
         tregistros.hsjornal AS hsjornal,
         ' ' AS hsmaquina
  FROM laa_pdtareasmanuales pdtareas
  INNER JOIN laa_pdtareasmanualesregistros tregistros ON tregistros.parent_id = pdtareas.id AND tregistros.estado <> 9
  LEFT JOIN laa_tareas tareas ON tareas.id = tregistros.tarea
  LEFT JOIN laa_legajos legajo_manual ON legajo_manual.id = tregistros.idlegajo
  LEFT JOIN ast_users usuario_empleado ON usuario_empleado.id = legajo_manual.user
  LEFT JOIN laa_clientes clientes ON clientes.id = pdtareas.cliente
  LEFT JOIN laa_fincas fincas ON fincas.id = pdtareas.finca
  LEFT JOIN laa_supervisores supervisores ON supervisores.idusuario = pdtareas.supervisor
  LEFT JOIN ast_users usuario_supervisor ON usuario_supervisor.id = supervisores.idusuario
  WHERE pdtareas.estado <> 9
    AND DATE(pdtareas.fecha) BETWEEN :fecha_desde AND :fecha_hasta

  UNION ALL

  SELECT
    'COSECHA' AS planilla,
    MIN(DATE_FORMAT(pdcosechas.fecha, '%Y-%m-%d')) AS fecha_tarea,
    MIN(CONCAT(
      CASE WHEN DAY(pdcosechas.fecha) <= 15 THEN '1' ELSE '2' END,
      '/', DATE_FORMAT(pdcosechas.fecha, '%b'), '/', DATE_FORMAT(pdcosechas.fecha, '%Y')
    )) AS quincena,
    MAX(clientes.nombre) AS nombre_cliente,
    MAX(fincas.nombre) AS nombre_finca,
    MAX(tareas.nombre) AS nombre_tarea,
    MAX({GRUPO_PAGO_EXPR}) AS grupo_pago,
    MAX(maquinarias.nombre) AS nombre_tractor,
    MAX(legajos_chofer.legajo) AS legajo,
    MAX(usuarios_chofer.name) AS nombre_empleado,
    MAX(usuarios_chofer.username) AS cuit,
    MAX(usuarios_supervisor.name) AS nombre_supervisor,
    ' ' AS nombre_capataz,
    ' ' AS implemento,
    0 AS unidades,
    0 AS tancadas,
    SUM(pdcosechas1.hsjornal) AS hsjornal,
    SUM(pdcosechas1.hsmaquina) AS hsmaquina
  FROM laa_pdcosechas pdcosechas
  INNER JOIN laa_pdcosechasregistros1 pdcosechas1 ON pdcosechas1.parent_id = pdcosechas.id AND pdcosechas1.estado <> 9
  LEFT JOIN laa_maquinarias maquinarias ON maquinarias.id = pdcosechas1.maquinaria
  LEFT JOIN laa_legajos legajos_chofer ON legajos_chofer.id = pdcosechas1.idlegajo
  LEFT JOIN ast_users usuarios_chofer ON usuarios_chofer.id = legajos_chofer.user
  LEFT JOIN laa_tareas tareas ON tareas.id = pdcosechas.tarea
  LEFT JOIN laa_supervisores supervisores ON supervisores.idusuario = pdcosechas.supervisor
  LEFT JOIN ast_users usuarios_supervisor ON usuarios_supervisor.id = supervisores.idusuario
  LEFT JOIN laa_clientes clientes ON clientes.id = pdcosechas.cliente
  LEFT JOIN laa_fincas fincas ON fincas.id = pdcosechas.finca
  WHERE pdcosechas.estado <> 9
    AND pdcosechas1.estado <> 9
    AND DATE(pdcosechas.fecha) BETWEEN :fecha_desde AND :fecha_hasta
  GROUP BY pdcosechas.id, pdcosechas1.id, legajos_chofer.id
) AS Tmpunion
ORDER BY Tmpunion.fecha_tarea
""")

QUERY_CLIENTES = text("""
    SELECT c.nombre FROM laa_clientes c
    WHERE c.estado <> 9
    ORDER BY c.nombre
""")

QUERY_FINCAS_POR_CLIENTE = text("""
    SELECT fincas.nombre AS nombre_finca
    FROM laa_fincas fincas
    LEFT JOIN laa_clientes cl ON cl.id = fincas.idcliente
    WHERE cl.estado <> 9
    AND cl.nombre = :cliente_nombre
    ORDER BY fincas.nombre
""")

QUERY_TAREAS = text("""
    SELECT ta.nombre AS nombre_tarea,
           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 1), ';', -1)) AS grupo_tarea,
           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 2), ';', -1)) AS grupo_pago,
           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 3), ';', -1)) AS grupo_factura
    FROM laa_tareas ta
    WHERE ta.estado <> 9
    ORDER BY ta.nombre
""")

QUERY_LEGAJOS = text("""
    SELECT users.name AS nombre,
           users.username AS cuil,
           legajos.legajo
    FROM laa_legajos legajos
    LEFT JOIN ast_users users ON legajos.user = users.id
""")


class ConsultaExternaService:

    def __init__(self, db_externa: Session):
        self.db = db_externa

    def obtener_tareas_quincena(self, quincena: date) -> list[dict]:
        fecha_desde, fecha_hasta = calcular_rango_quincena(quincena)

        t0 = time.time()
        resultado = self.db.execute(
            QUERY_PRINCIPAL,
            {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta}
        )
        t1 = time.time()
        filas = resultado.fetchall()
        t2 = time.time()

        print(f"[TIMING] execute: {t1-t0:.2f}s | fetchall: {t2-t1:.2f}s | total: {t2-t0:.2f}s")

        columnas = resultado.keys()
        return [dict(zip(columnas, fila)) for fila in filas]

    def obtener_clientes(self) -> list[str]:
        resultado = self.db.execute(QUERY_CLIENTES)
        return [fila[0] for fila in resultado.fetchall()]

    def obtener_fincas(self, cliente_nombre: str) -> list[str]:
        resultado = self.db.execute(
            QUERY_FINCAS_POR_CLIENTE, {"cliente_nombre": cliente_nombre}
        )
        return [fila[0] for fila in resultado.fetchall()]

    def obtener_tareas(self) -> list[dict]:
        resultado = self.db.execute(QUERY_TAREAS)
        return [
            {"nombre": fila[0], "grupo_tarea": fila[1], "grupo_pago": fila[2], "grupo_factura": fila[3]}
            for fila in resultado.fetchall()
        ]

    def obtener_legajos(self) -> list[dict]:
        resultado = self.db.execute(QUERY_LEGAJOS)
        return [
            {"nombre": fila[0], "cuil": fila[1], "legajo": fila[2]}
            for fila in resultado.fetchall()
        ]