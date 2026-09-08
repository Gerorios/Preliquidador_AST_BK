"""Descripción de un módulo del sistema (ADR-0013). Cada módulo construye su
ModuloInfo en app/modulos/<m>/__init__.py; app/modulos/__init__.py los lista.
El núcleo consume la lista y no conoce módulos por nombre."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuloInfo:
    clave: str
    nombre: str
    descripcion: str
    activo: bool
    routers: tuple = ()
    etiquetas_rol: dict = field(default_factory=dict)
    panel_gerencial: bool = False
    modelos: str = ""
    """Ruta importable del módulo de modelos (p. ej. "app.modulos.preliquidacion.models").
    Se importa al arrancar para registrar sus tablas en Base.metadata (chequeo de tablas
    faltantes)."""

    def publico(self) -> dict:
        """Lo que se expone por la API (sin routers)."""
        return {
            "clave": self.clave, "nombre": self.nombre, "descripcion": self.descripcion,
            "etiquetas_rol": dict(self.etiquetas_rol), "panel_gerencial": self.panel_gerencial,
        }
