"""Lectura del sistema de campo (ADCP), sólo lectura, con SQL crudo y text().

Por ahora una sola consulta: el maestro de tareas, con el id que usan los
partes. La Unidad sugerida y la marca No facturable de cada tarea se leen en
vivo de acá, del tercer segmento de su descripción, y Facturación no guarda
copia (docs/superpowers/plans/2026-10-12-unidad-desde-campo.md).

Preliquidación lee el mismo maestro, pero un módulo no importa a otro
(ADR-0013): el SQL se copia. La traducción de errores y los timeouts son del
núcleo (app/core/database.py): acá no se configuran.
"""

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

    def __init__(self, db_externa: Session):
        self.db = db_externa

    def _ejecutar(self, query, params=None):
        """Todas las consultas al campo pasan por acá: si venció el
        read_timeout o el servidor de ADCP no está, pymysql levanta
        OperationalError y el núcleo lo traduce a ExternaNoDisponible, que
        main.py convierte en 503 con un mensaje que la persona entienda."""
        with traducir_errores_externa():
            return self.db.execute(query, params or {}).fetchall()

    def obtener_tareas(self) -> list[dict]:
        """Las tareas activas del campo, en el orden del campo (por nombre),
        cada una con {tarea_id, nombre, grupo_tarea, unidad_sugerida,
        no_facturable}.

        La descripción se corta por ";". Sin grupo es siempre None (vacía,
        NULL o sólo espacios). La unidad es el tercer segmento, y sólo si hay
        tres o más: con dos, el segundo es el grupo de pago. traducir_unidad
        da la clave, la marca No facturable, o Sin definir (None, False). Sólo
        van los valores traducidos, sin el texto crudo."""
        filas = self._ejecutar(QUERY_TAREAS)
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
