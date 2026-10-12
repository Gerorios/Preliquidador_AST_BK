"""Modelos SQLAlchemy del módulo Facturación.

Espejo de las migraciones de `migrations/facturacion/`. **La fuente de verdad
del esquema son ellas, no esto** (regla 9 de GUIA-MODULOS): acá se declara lo
mismo para que el ORM pueda leer y escribir, y para que el chequeo de tablas
faltantes del arranque cubra al módulo.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base
# Usuario vive en el núcleo. Se importa acá a propósito: `actualizado_por` tiene
# ForeignKey("usuarios.id"), que SQLAlchemy resuelve por nombre, así que importar
# este módulo tiene que registrar Usuario primero. No borrar.
from app.core.models import Usuario, ahora_utc  # noqa: F401


class TareaFacturacion(Base):
    """Qué se le factura a una tarea del sistema de campo (001).

    Una fila por cada tarea que tiene algo definido; **sin fila = Sin
    definir**. Cada fila tiene exactamente una de las dos cosas: una Unidad
    sugerida (una clave de `unidades.UNIDADES`) o la marca No facturable. La
    base no lo controla: lo controla el servicio, y volver a Sin definir borra
    la fila.

    La tarea se identifica por su id en el campo (`tarea_id`) y no por el
    nombre: los partes la apuntan por id, un renombre no pierde la unidad y
    nada garantiza que el nombre sea único. Si el campo da de baja la tarea, la
    fila no se borra: el Cruce todavía puede necesitarla para partes viejos.
    """
    __tablename__ = "facturacion_tarea"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    tarea_id        = Column(Integer, nullable=False)
    unidad_sugerida = Column(String(20), nullable=True)
    no_facturable   = Column(Boolean, nullable=False, default=False)
    actualizado_en  = Column(DateTime, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    # NULL = la cargó el script de la primera carga, no una persona.
    actualizado_por = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tarea_id", name="uq_facturacion_tarea_tarea_id"),
    )
