"""La Unidad sugerida o la marca No facturable de cada tarea del campo.

Una fila de facturacion_tarea por tarea con algo definido; sin fila = Sin
definir. Cada fila tiene exactamente una de las dos cosas, y lo controla este
servicio y no la base: lo comparten la API y el script de la primera carga.

Las tareas del campo llegan de afuera (ConsultaExternaService.obtener_tareas),
para que el servicio no lea el campo por su cuenta y se pueda probar con listas.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.models import ahora_utc
from app.modulos.facturacion.models import TareaFacturacion
from app.modulos.facturacion.unidades import UNIDADES


class DefinicionInvalida(ValueError):
    """Lo que se quiso guardar no es una definición válida. El mensaje lo lee
    una persona tal cual (la API lo devuelve como 422)."""


class TareaNoEncontrada(LookupError):
    """La tarea no está entre las activas del sistema de campo (404)."""


def _item(tarea: dict, fila: TareaFacturacion | None) -> dict:
    unidad = fila.unidad_sugerida if fila else None
    no_facturable = bool(fila.no_facturable) if fila else False
    return {
        "tarea_id": tarea["tarea_id"],
        "nombre": tarea["nombre"],
        "grupo_tarea": tarea["grupo_tarea"],
        "unidad_sugerida": unidad,
        "no_facturable": no_facturable,
        "sin_definir": unidad is None and not no_facturable,
    }


class UnidadService:

    def __init__(self, db: Session):
        self.db = db

    def listar(self, tareas_del_campo: list[dict]) -> list[dict]:
        """Cada tarea activa del campo con lo que tiene definido: primero las
        Sin definir, y dentro de cada grupo el orden en que llegan del campo.

        Las filas de tareas que el campo dio de baja no aparecen, pero no se
        borran: el Cruce todavía puede necesitarlas para partes viejos."""
        filas = {f.tarea_id: f for f in self.db.query(TareaFacturacion).all()}
        items = [_item(t, filas.get(t["tarea_id"])) for t in tareas_del_campo]
        # sorted es estable: cada grupo conserva el orden del campo.
        return sorted(items, key=lambda i: not i["sin_definir"])

    def definir(self, tareas_del_campo: list[dict], tarea_id: int,
                unidad_sugerida: str | None, no_facturable: bool,
                usuario_id: int | None) -> dict:
        """Deja la tarea con la Unidad sugerida, con la marca No facturable o
        Sin definir (las dos vacías, que borra la fila). Devuelve el ítem con
        la misma forma que listar."""
        if unidad_sugerida is not None and no_facturable:
            raise DefinicionInvalida(
                "Una tarea tiene Unidad sugerida o es No facturable, no las dos.")
        if unidad_sugerida is not None and unidad_sugerida not in UNIDADES:
            raise DefinicionInvalida(
                f"Unidad de facturación desconocida: {unidad_sugerida}.")

        tarea = next((t for t in tareas_del_campo if t["tarea_id"] == tarea_id), None)
        if tarea is None:
            raise TareaNoEncontrada(
                "La tarea no está entre las activas del sistema de campo.")

        try:
            return self._escribir(tarea, unidad_sugerida, no_facturable, usuario_id)
        except (IntegrityError, StaleDataError):
            # Otra persona creó o borró la fila entre la lectura y el commit.
            # Gana la última que guarda: se repite una vez sobre lo que haya.
            self.db.rollback()
            return self._escribir(tarea, unidad_sugerida, no_facturable, usuario_id)

    def _escribir(self, tarea: dict, unidad_sugerida: str | None,
                  no_facturable: bool, usuario_id: int | None) -> dict:
        tarea_id = tarea["tarea_id"]
        fila = self.db.query(TareaFacturacion).filter_by(tarea_id=tarea_id).one_or_none()
        if unidad_sugerida is None and not no_facturable:
            if fila is not None:
                self.db.delete(fila)
                self.db.commit()
            return _item(tarea, None)

        if fila is None:
            fila = TareaFacturacion(tarea_id=tarea_id)
            self.db.add(fila)
        fila.unidad_sugerida = unidad_sugerida
        fila.no_facturable = no_facturable
        fila.actualizado_por = usuario_id
        fila.actualizado_en = ahora_utc()
        self.db.commit()
        return _item(tarea, fila)
