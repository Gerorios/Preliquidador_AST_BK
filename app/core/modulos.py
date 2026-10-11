"""Descripción de un módulo del sistema (ADR-0013). Cada módulo construye su
ModuloInfo en app/modulos/<m>/__init__.py; app/modulos/__init__.py los lista.
El núcleo consume la lista y no conoce módulos por nombre."""
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Pantalla:
    """Pantalla de un módulo, la unidad de permiso de los roles (ADR-0020).

    `clave` se guarda en la base (rol_permiso.pantalla) y no cambia. `editable` en
    False quiere decir que la pantalla sólo admite Ver. `requiere` son claves de
    otras pantallas del mismo módulo que hay que poder ver para llegar a esta (p. ej.
    Revisión se abre desde el Inicio del módulo)."""
    clave: str
    nombre: str
    editable: bool = True
    requiere: tuple[str, ...] = ()

    def publico(self) -> dict:
        return {
            "clave": self.clave, "nombre": self.nombre, "editable": self.editable,
            "requiere": list(self.requiere),
        }


@dataclass(frozen=True)
class ModuloInfo:
    clave: str
    nombre: str
    descripcion: str
    activo: bool
    routers: tuple = ()
    panel_gerencial: bool = False
    modelos: str = ""
    """Ruta importable del módulo de modelos (p. ej. "app.modulos.preliquidacion.models").
    Se importa al arrancar para registrar sus tablas en Base.metadata (chequeo de tablas
    faltantes)."""
    pantallas: tuple = ()
    """Pantallas del módulo (tuple de Pantalla), en el orden del editor de roles."""

    def publico(self) -> dict:
        """Lo que se expone por la API (sin routers)."""
        return {
            "clave": self.clave, "nombre": self.nombre, "descripcion": self.descripcion,
            "panel_gerencial": self.panel_gerencial,
            "pantallas": [p.publico() for p in self.pantallas],
        }


def catalogo_activo(request: Request) -> tuple[ModuloInfo, ...]:
    """Dependencia: los módulos activos, con sus pantallas. Los carga
    `app/main.py` en `app.state.modulos` al registrar los routers; así el núcleo
    (la Administración) valida claves de módulo y pantalla sin importar
    módulos."""
    return request.app.state.modulos
