"""Lectura del sistema de campo (ADCP) y de la base de sueldos, sólo lectura,
con SQL crudo y text().

Del campo: el maestro de tareas, con el id que usan los partes (la Unidad
sugerida y la marca No facturable se leen en vivo del tercer segmento de su
descripción, y Facturación no guarda copia:
docs/superpowers/plans/2026-10-12-unidad-desde-campo.md), y los clientes y
las fincas, con id, para los Comprobantes. De sueldos: las Empresas emisoras.

Preliquidación lee los mismos maestros, pero un módulo no importa a otro
(ADR-0013): el SQL se copia. La traducción de errores y los timeouts son del
núcleo (app/core/database.py): acá no se configuran.
"""

import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import traducir_errores_externa
from app.modulos.facturacion.unidades import traducir_unidad

# El maestro de tareas: la misma tabla, el mismo filtro de bajas y el mismo
# orden que QUERY_TAREAS de Preliquidación, más el id. La `descripcion` viene
# cruda y se corta en Python (obtener_tareas): el primer segmento es el grupo
# de tareas y el tercero, la unidad. Con SUBSTRING_INDEX, una descripción de
# dos segmentos devolvería el segundo, que es el grupo de pago. El grupo de
# pago y el grupo_factura no los usa este módulo.
QUERY_TAREAS = text("""
    SELECT ta.id AS tarea_id,
           ta.nombre AS nombre_tarea,
           ta.descripcion AS descripcion
    FROM laa_tareas ta
    WHERE ta.estado <> 9
    ORDER BY ta.nombre
""")

# La misma, con las dadas de baja: el histórico resuelve tareas por nombre y
# la planilla vieja nombra tareas que hoy están de baja.
QUERY_TAREAS_CON_BAJA = text("""
    SELECT ta.id AS tarea_id,
           ta.nombre AS nombre_tarea,
           ta.descripcion AS descripcion
    FROM laa_tareas ta
    ORDER BY ta.nombre
""")

# Clientes y fincas: las consultas de Preliquidación, con el id. Activo usa la
# misma regla que el filtro (estado distinto de 9; un NULL no cuenta), para
# que un cliente no sea activo en una lectura y de baja en la otra.
QUERY_CLIENTES = text("""
    SELECT c.id, c.nombre
    FROM laa_clientes c
    WHERE c.estado <> 9
    ORDER BY c.nombre
""")

QUERY_CLIENTES_CON_BAJA = text("""
    SELECT c.id, c.nombre,
           CASE WHEN c.estado <> 9 THEN 1 ELSE 0 END AS activo
    FROM laa_clientes c
    ORDER BY c.nombre
""")

# Las fincas de un cliente, por su id. No exige que el cliente esté activo:
# un Comprobante puede conservar un cliente que pasó a baja (plan de la E2,
# regla 7) y sus Líneas siguen validando la finca contra él.
QUERY_FINCAS_DE_CLIENTE = text("""
    SELECT f.id, f.nombre
    FROM laa_fincas f
    WHERE f.idcliente = :cliente_id
      AND f.estado <> 9
    ORDER BY f.nombre
""")

# Todas las fincas activas con su cliente, para el script del histórico.
QUERY_TODAS_LAS_FINCAS = text("""
    SELECT f.id, f.nombre, f.idcliente AS cliente_id
    FROM laa_fincas f
    WHERE f.estado <> 9
    ORDER BY f.idcliente, f.nombre
""")

# Las Empresas emisoras: la consulta del endpoint de empresas de
# Preliquidación, copiada (plan de la E2, regla 8: si aparece un tercer uso,
# se sube al núcleo).
QUERY_EMPRESAS = text(
    "SELECT DISTINCT empresa FROM nuempleados "
    "WHERE borrado IS NULL OR borrado <> 'S' "
    "ORDER BY empresa"
)


# Caché de proceso de clientes, fincas por cliente y empresas, como la de
# empresas de Preliquidación: cambian casi nunca y la base de campo es lenta.
# La clave distingue cada lectura (y el cliente, en las fincas). Un error no
# se guarda: la próxima llamada vuelve a consultar.
_CACHE_TTL = 600  # segundos
_CACHE: dict = {}


def _reloj() -> float:
    """El reloj de la caché; los tests lo reemplazan."""
    return time.monotonic()


def invalidar_cache():
    _CACHE.clear()


def _cacheado(clave, leer):
    guardado = _CACHE.get(clave)
    if guardado is not None and guardado[0] > _reloj():
        return guardado[1]
    datos = leer()
    _CACHE[clave] = (_reloj() + _CACHE_TTL, datos)
    return datos


def normalizar_nombre(nombre) -> str:
    """El nombre de una tarea listo para comparar: sin espacios en los bordes,
    con los espacios internos colapsados y en mayúsculas.

    Es como tarea_canonica de Preliquidación, con dos diferencias: colapsa los
    espacios internos (los nombres pueden traer dobles espacios) y no aplica el
    alias de pago de ADR-0012, porque la Unidad sugerida es de cada tarea del
    campo y no de cómo se le paga a quien la hizo. Hoy no la llama nadie: la
    conserva la E2."""
    return " ".join((nombre or "").split()).upper()


class ConsultaExternaService:

    def __init__(self, db_externa: Session, db_sueldos: Session | None = None):
        """La sesión de sueldos es opcional: sólo la usa empresas(), y así
        quien lee sólo el campo (las tareas) no abre otra conexión."""
        self.db = db_externa
        self.db_sueldos = db_sueldos

    def _ejecutar(self, query, params=None, db=None):
        """Todas las consultas pasan por acá: si venció el read_timeout o el
        servidor no está, pymysql levanta OperationalError y el núcleo lo
        traduce a ExternaNoDisponible, que main.py convierte en 503 con un
        mensaje que la persona entienda. Por defecto va al campo; empresas()
        pasa la sesión de sueldos."""
        with traducir_errores_externa():
            return (db or self.db).execute(query, params or {}).fetchall()

    def clientes(self, incluir_baja: bool = False) -> list[dict]:
        """Los clientes del campo por nombre, cada uno con {id, nombre,
        activo}. Sólo los activos, salvo con incluir_baja (el histórico), que
        trae también los de baja con activo=False. Con caché de 10 minutos."""
        if incluir_baja:
            return _cacheado(("clientes", True), lambda: [
                {"id": id_, "nombre": nombre, "activo": bool(activo)}
                for id_, nombre, activo in self._ejecutar(QUERY_CLIENTES_CON_BAJA)
            ])
        return _cacheado(("clientes", False), lambda: [
            {"id": id_, "nombre": nombre, "activo": True}
            for id_, nombre in self._ejecutar(QUERY_CLIENTES)
        ])

    def fincas_de_cliente(self, cliente_id: int) -> list[dict]:
        """Las fincas activas de un cliente, {id, nombre}, por nombre. Con
        caché de 10 minutos por cliente."""
        return _cacheado(("fincas", cliente_id), lambda: [
            {"id": id_, "nombre": nombre}
            for id_, nombre in self._ejecutar(
                QUERY_FINCAS_DE_CLIENTE, {"cliente_id": cliente_id})
        ])

    def todas_las_fincas(self) -> list[dict]:
        """Todas las fincas activas, {id, nombre, cliente_id}, para el script
        del histórico. Sin caché: el script la lee una vez por corrida."""
        return [
            {"id": id_, "nombre": nombre, "cliente_id": cliente_id}
            for id_, nombre, cliente_id in self._ejecutar(QUERY_TODAS_LAS_FINCAS)
        ]

    def empresas(self) -> list[str]:
        """Las Empresas emisoras, de la base de sueldos: recortadas, sin
        vacías ni repetidas, ordenadas. Con caché de 10 minutos."""
        if self.db_sueldos is None:
            raise RuntimeError(
                "ConsultaExternaService.empresas() necesita la sesión de sueldos")
        return _cacheado(("empresas",), lambda: sorted({
            empresa.strip()
            for (empresa,) in self._ejecutar(QUERY_EMPRESAS, db=self.db_sueldos)
            if empresa and empresa.strip()
        }))

    def obtener_tareas(self, incluir_baja: bool = False) -> list[dict]:
        """Las tareas del campo, en el orden del campo (por nombre), cada una
        con {tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}.
        Sólo las activas, salvo con incluir_baja (el histórico), que trae
        también las dadas de baja, armadas igual.

        La descripción se corta por ";". Sin grupo es siempre None (vacía,
        NULL o sólo espacios). La unidad es el tercer segmento, y sólo si hay
        tres o más: con dos, el segundo es el grupo de pago. traducir_unidad
        da la clave, la marca No facturable, o Sin definir (None, False). Sólo
        van los valores traducidos, sin el texto crudo."""
        filas = self._ejecutar(QUERY_TAREAS_CON_BAJA if incluir_baja else QUERY_TAREAS)
        tareas = []
        for tarea_id, nombre, descripcion in filas:
            partes = (descripcion or "").split(";")
            texto_unidad = partes[2] if len(partes) >= 3 else ""
            unidad_sugerida, no_facturable = traducir_unidad(texto_unidad)
            tareas.append({
                "tarea_id": tarea_id,
                "nombre": nombre,
                "grupo_tarea": partes[0].strip() or None,
                "unidad_sugerida": unidad_sugerida,
                "no_facturable": no_facturable,
            })
        return tareas
