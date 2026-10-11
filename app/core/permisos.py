"""
Permisos por pantalla (ADR-0020).

- `usuarios.rol` es GLOBAL: 'admin' pasa todo sin necesitar permisos.
- Cada persona tiene roles (`Usuario.roles`); cada rol da Ver o Editar por
  pantalla de un módulo. El permiso efectivo es el máximo entre sus roles, y
  Editar incluye Ver. "Sin acceso" es que no haya permiso.
- Cada módulo declara sus pantallas (`ModuloInfo.pantallas`) y sus
  dependencias con `requiere_pantalla`, una vez por archivo (p. ej.
  app/modulos/preliquidacion/permisos.py); cada dependencia expone
  `.requisito` para que los tests lean el mapa de permisos desde `app.routes`.
  El núcleo no conoce módulos ni pantallas por nombre.
- La restricción vive en el backend; el frontend sólo esconde lo que no
  corresponde.

Nota de import: este módulo importa `get_usuario_actual` de `app.core.auth` a
nivel de módulo. Por eso `auth.py` NO debe importar `permisos` a nivel de
módulo (para evitar el ciclo): importa `permisos_de` dentro de
`_permisos_de_sesion`, no arriba del archivo.
"""
from fastapi import Depends, HTTPException, status

from app.core.auth import get_usuario_actual
from app.core.models import Usuario

NIVELES = ("ver", "editar")  # de menor a mayor: Editar incluye Ver

_SIN_PERMISO = "No tenés permiso para esta operación"


def permisos_de(usuario) -> dict[str, dict[str, str]]:
    """{'preliquidacion': {'conceptos': 'editar', ...}, ...}: el máximo entre los
    roles de la persona. Tolera objetos sin `roles`. Al admin no le hacen falta:
    lo resuelven `puede` y `requiere_pantalla`."""
    efectivos: dict[str, dict[str, str]] = {}
    for rol in getattr(usuario, "roles", None) or []:
        for permiso in getattr(rol, "permisos", None) or []:
            del_modulo = efectivos.setdefault(permiso.modulo, {})
            actual = del_modulo.get(permiso.pantalla)
            if actual is None or NIVELES.index(permiso.nivel) > NIVELES.index(actual):
                del_modulo[permiso.pantalla] = permiso.nivel
    return efectivos


def _alcanza(permisos: dict[str, dict[str, str]], modulo: str, pantalla: str, nivel: str) -> bool:
    tiene = permisos.get(modulo, {}).get(pantalla)
    return tiene is not None and NIVELES.index(tiene) >= NIVELES.index(nivel)


def puede(usuario, modulo: str, pantalla: str, nivel: str = "ver") -> bool:
    """¿La persona tiene al menos `nivel` en esa pantalla? El admin pasa todo."""
    if getattr(usuario, "rol", None) == "admin":
        return True
    return _alcanza(permisos_de(usuario), modulo, pantalla, nivel)


def requiere_pantalla(modulo: str, *pantallas: str, nivel: str = "ver"):
    """Dependency de autorización: exige `nivel` en al menos una de `pantallas`
    del módulo (o admin). Definirla una sola vez por archivo: FastAPI cachea por
    objeto. Expone `.requisito` = (modulo, pantallas, nivel)."""
    if nivel not in NIVELES:
        raise ValueError(f"Nivel inválido {nivel!r}: tiene que ser uno de {NIVELES}")
    if not pantallas:
        raise ValueError("requiere_pantalla necesita al menos una pantalla")

    def dependencia(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if getattr(usuario, "rol", None) != "admin":
            permisos = permisos_de(usuario)
            if not any(_alcanza(permisos, modulo, p, nivel) for p in pantallas):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_SIN_PERMISO)
        return usuario

    dependencia.requisito = (modulo, tuple(pantallas), nivel)
    return dependencia


def requiere_admin():
    """Dependency de autorización para lo que administra el Sistema (usuarios,
    roles): exige el rol GLOBAL 'admin'. A diferencia de `requiere_pantalla`,
    no hay rol ni permiso de pantalla que alcance — ver CONTEXT.md, "Admin"."""
    def dependencia(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if getattr(usuario, "rol", None) != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un administrador puede hacer esto",
            )
        return usuario
    dependencia.requisito = "admin"
    return dependencia
