"""Lectura del sistema de campo (ADCP), sólo lectura, con SQL crudo y text().

Por ahora una sola consulta: el maestro de tareas, con el id que usan los
partes. Facturación guarda la Unidad sugerida por ese id (plan de la E1, D3),
no por el nombre.

Preliquidación lee el mismo maestro, pero un módulo no importa a otro
(ADR-0013): el SQL se copia. La traducción de errores y los timeouts son del
núcleo (app/core/database.py): acá no se configuran.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import traducir_errores_externa

# El maestro de tareas: la misma tabla, el mismo filtro de bajas y el mismo
# orden que QUERY_TAREAS de Preliquidación, más el id. El grupo de tareas es el
# primer segmento de `descripcion`; el grupo de pago y el grupo_factura no los
# usa este módulo.
QUERY_TAREAS = text("""
    SELECT ta.id AS tarea_id,
           ta.nombre AS nombre_tarea,
           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ta.descripcion, ';', 1), ';', -1)) AS grupo_tarea
    FROM laa_tareas ta
    WHERE ta.estado <> 9
    ORDER BY ta.nombre
""")


def normalizar_nombre(nombre) -> str:
    """El nombre de una tarea listo para comparar: sin espacios en los bordes,
    con los espacios internos colapsados y en mayúsculas.

    Es como tarea_canonica de Preliquidación, con dos diferencias: colapsa los
    espacios internos (el maestro de la planilla trae dobles espacios) y no
    aplica el alias de pago de ADR-0012, porque la Unidad sugerida es de cada
    tarea del campo y no de cómo se le paga a quien la hizo."""
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
        """Las tareas activas del campo, en el orden del campo (por nombre).

        Sin grupo es siempre None: una descripción vacía da "" y una NULL da
        None, y el contrato de la API tiene un solo valor para eso."""
        filas = self._ejecutar(QUERY_TAREAS)
        return [
            {"tarea_id": fila[0], "nombre": fila[1], "grupo_tarea": (fila[2] or "").strip() or None}
            for fila in filas
        ]
