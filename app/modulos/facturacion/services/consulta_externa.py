"""Lectura del sistema de campo (ADCP), sólo lectura, con SQL crudo y text().

Por ahora una sola consulta: el maestro de tareas, con el id que usan los
partes. Facturación guarda la Unidad sugerida por ese id (plan de la E1, D3),
no por el nombre.

Preliquidación lee el mismo maestro, pero un módulo no importa a otro
(ADR-0013): el SQL y la traducción de errores se copian. Los timeouts son del
engine del núcleo (app/core/database.py): acá no se configuran.
"""
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import ExternaNoDisponible

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

# Códigos de MySQL en los que ADCP contesta pero nos niega el acceso
# (credenciales o permisos cambiados): reintentar no sirve, a diferencia de un
# corte o un timeout. Cualquier otro código se trata como "no respondió".
CODIGOS_ACCESO_RECHAZADO = {1044, 1045, 1142, 1143}


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
        OperationalError y acá se traduce a ExternaNoDisponible, que main.py
        convierte en 503 con un mensaje que la persona entienda. Los mensajes
        son los mismos que los de Preliquidación."""
        t0 = time.time()
        try:
            return self.db.execute(query, params or {}).fetchall()
        except OperationalError as e:
            codigo = (getattr(e.orig, "args", None) or (None,))[0]
            print(f"[EXTERNA] error {codigo} tras {time.time()-t0:.1f}s: {e.orig}")
            if codigo in CODIGOS_ACCESO_RECHAZADO:
                raise ExternaNoDisponible(
                    "La base de datos de campo (ADCP) rechazó el acceso del sistema. "
                    "Reintentar no sirve: avisá a sistemas."
                ) from e
            raise ExternaNoDisponible(
                "La base de datos de campo (ADCP) no respondió a tiempo. "
                "Reintentá en unos minutos."
            ) from e

    def obtener_tareas(self) -> list[dict]:
        """Las tareas activas del campo, en el orden del campo (por nombre).

        Sin grupo es siempre None: una descripción vacía da "" y una NULL da
        None, y el contrato de la API tiene un solo valor para eso."""
        filas = self._ejecutar(QUERY_TAREAS)
        return [
            {"tarea_id": fila[0], "nombre": fila[1], "grupo_tarea": (fila[2] or "").strip() or None}
            for fila in filas
        ]
