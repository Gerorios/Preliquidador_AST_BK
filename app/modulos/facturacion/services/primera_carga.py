"""La primera carga de Unidades sugeridas desde el maestro de tareas de la
planilla (plan de la E1, D7). Lógica pura: el script
scripts/importar_unidades_del_maestro.py es sólo la cáscara.

El maestro es un CSV (`nombre_tarea;grupo_tarea;grupo_factura`, UTF-8 con BOM)
que viene por nombre de tarea. Se cruza contra las tareas activas del campo
con normalizar_nombre de los dos lados, y se traduce a tarea_id una sola vez.

**Sólo se completa lo vacío.** Una tarea que ya tiene fila no se toca, aunque
el CSV diga otra cosa: lo que alguien definió en la pantalla vale más que la
planilla. Esas se listan, para que se vea la diferencia.

**Lo que no es claro no se carga.** Un nombre que el campo tiene dos veces, o
que el CSV repite con grupos distintos, queda Sin definir y se lista: adivinar
ahí sería guardar una unidad que nadie decidió.
"""
import csv
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.modulos.facturacion.models import TareaFacturacion
from app.modulos.facturacion.services.consulta_externa import normalizar_nombre
from app.modulos.facturacion.unidades import NO_FACTURABLE_PLANILLA, UNIDAD_DE_PLANILLA

COLUMNAS = ("nombre_tarea", "grupo_tarea", "grupo_factura")


class MaestroInvalido(ValueError):
    """El archivo no tiene el formato del maestro. El mensaje lo lee quien
    corre el script."""


@dataclass
class PlanDeCarga:
    """Qué haría la carga, por secciones del informe. Los nombres son los del
    CSV (sin espacios en los bordes), salvo en faltan_en_csv, que son del campo."""
    # {"tarea_id", "nombre", "unidad_sugerida", "no_facturable"}
    a_cargar: list = field(default_factory=list)
    sin_grupo: list = field(default_factory=list)            # nombre
    grupo_desconocido: list = field(default_factory=list)    # (nombre, grupo)
    no_activa: list = field(default_factory=list)            # nombre
    ambigua_en_campo: list = field(default_factory=list)     # (nombre, [tarea_id, ...])
    repetida_en_csv: list = field(default_factory=list)      # (nombre, [grupo, ...])
    # {"tarea_id", "nombre", "actual", "csv"}; actual y csv = (unidad, no_facturable)
    ya_definidas: list = field(default_factory=list)
    faltan_en_csv: list = field(default_factory=list)        # {"tarea_id", "nombre"}

    @property
    def contradichas(self) -> list:
        """Las ya definidas en las que el CSV dice otra cosa."""
        return [d for d in self.ya_definidas if d["actual"] != d["csv"]]

    @property
    def unidades_a_cargar(self) -> int:
        return sum(1 for c in self.a_cargar if not c["no_facturable"])

    @property
    def no_facturables_a_cargar(self) -> int:
        return sum(1 for c in self.a_cargar if c["no_facturable"])


def leer_maestro(ruta) -> list[dict]:
    """Las filas del CSV como diccionarios con las tres columnas, tal como
    vienen. Valida el encabezado: otro formato es un MaestroInvalido."""
    with Path(ruta).open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        encabezado = [c.strip() for c in next(lector, [])]
        if tuple(encabezado) != COLUMNAS:
            raise MaestroInvalido(
                "El CSV no tiene el encabezado del maestro de tareas: se esperaba "
                f"'{';'.join(COLUMNAS)}' y tiene '{';'.join(encabezado)}'.")
        filas = []
        for valores in lector:
            if not any(v.strip() for v in valores):
                continue
            valores = (valores + [""] * len(COLUMNAS))[:len(COLUMNAS)]
            filas.append(dict(zip(COLUMNAS, valores)))
        return filas


def _valor_del_grupo(grupo: str):
    """(unidad, no_facturable) para un grupo de la planilla ya normalizado, o
    None si no es ni una unidad ni la marca."""
    if grupo == NO_FACTURABLE_PLANILLA:
        return (None, True)
    if grupo in UNIDAD_DE_PLANILLA:
        return (UNIDAD_DE_PLANILLA[grupo], False)
    return None


def planificar(filas: list[dict], tareas_del_campo: list[dict], definidas: dict) -> PlanDeCarga:
    """Arma el plan sin escribir nada.

    `definidas` es {tarea_id: (unidad_sugerida, no_facturable)} de las tareas
    que ya tienen fila (ver `definidas()`)."""
    plan = PlanDeCarga()

    # El CSV por nombre normalizado, en el orden del archivo.
    por_nombre: dict[str, dict] = {}
    for fila in filas:
        clave = normalizar_nombre(fila["nombre_tarea"])
        if not clave:
            continue
        entrada = por_nombre.setdefault(
            clave, {"nombre": fila["nombre_tarea"].strip(), "grupos": []})
        grupo = normalizar_nombre(fila["grupo_factura"])
        if grupo not in entrada["grupos"]:
            entrada["grupos"].append(grupo)

    # El campo por nombre normalizado.
    ids_por_nombre: dict[str, list[int]] = {}
    for t in tareas_del_campo:
        ids_por_nombre.setdefault(normalizar_nombre(t["nombre"]), []).append(t["tarea_id"])

    for clave, entrada in por_nombre.items():
        nombre, grupos = entrada["nombre"], entrada["grupos"]
        if len(grupos) > 1:
            plan.repetida_en_csv.append((nombre, sorted(grupos)))
            continue
        grupo = grupos[0]
        if not grupo:
            plan.sin_grupo.append(nombre)
            continue
        valor = _valor_del_grupo(grupo)
        if valor is None:
            plan.grupo_desconocido.append((nombre, grupo))
            continue
        ids = ids_por_nombre.get(clave, [])
        if not ids:
            plan.no_activa.append(nombre)
            continue
        if len(ids) > 1:
            plan.ambigua_en_campo.append((nombre, sorted(ids)))
            continue
        tarea_id = ids[0]
        if tarea_id in definidas:
            plan.ya_definidas.append({
                "tarea_id": tarea_id, "nombre": nombre,
                "actual": definidas[tarea_id], "csv": valor,
            })
            continue
        plan.a_cargar.append({
            "tarea_id": tarea_id, "nombre": nombre,
            "unidad_sugerida": valor[0], "no_facturable": valor[1],
        })

    plan.faltan_en_csv = [
        {"tarea_id": t["tarea_id"], "nombre": t["nombre"]}
        for t in tareas_del_campo
        if normalizar_nombre(t["nombre"]) not in por_nombre
    ]
    return plan


def definidas(db: Session) -> dict:
    """{tarea_id: (unidad_sugerida, no_facturable)} de las filas que ya hay."""
    return {
        f.tarea_id: (f.unidad_sugerida, bool(f.no_facturable))
        for f in db.query(TareaFacturacion).all()
    }


def aplicar(db: Session, plan: PlanDeCarga) -> int:
    """Inserta lo que el plan carga y devuelve cuántas filas escribió.

    Sin persona (`actualizado_por` en NULL): así se distingue lo que puso la
    carga de lo que alguien cambió después, y se puede deshacer sólo lo suyo.
    Vuelve a mirar qué tiene fila, por si alguien definió una tarea entre el
    plan y la escritura: esa no se pisa."""
    ya = set(definidas(db))
    nuevas = [
        TareaFacturacion(
            tarea_id=c["tarea_id"], unidad_sugerida=c["unidad_sugerida"],
            no_facturable=c["no_facturable"], actualizado_por=None,
        )
        for c in plan.a_cargar if c["tarea_id"] not in ya
    ]
    db.add_all(nuevas)
    db.commit()
    return len(nuevas)
