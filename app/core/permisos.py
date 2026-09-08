"""
Permisos por módulo (ADR-0013).

- `usuarios.rol` es GLOBAL: 'admin' ve y opera todo; 'usuario' depende de usuario_modulo.
- `usuario_modulo` da, por módulo, 'operador' (opera el circuito) o 'gerente' (panel
  gerencial y lo que el módulo le abra). Ver CONTEXT.md, "Sistema y módulos".

Cada módulo define sus dependencias concretas sobre `requiere_modulo`
(p. ej. app/modulos/preliquidacion/permisos.py). El núcleo no conoce módulos
por nombre salvo esta lista, que crece cuando se registra uno nuevo.

Nota de import: este módulo importa `get_usuario_actual` de `app.core.auth` a
nivel de módulo. Por eso `auth.py` NO debe importar `permisos` a nivel de
módulo (para evitar el ciclo) — en Task 2, `auth.py` importa `modulos_de`
dentro de las funciones (`login`/`me`), no arriba del archivo.
"""
from fastapi import Depends, HTTPException, status

from app.core.auth import get_usuario_actual
from app.core.models import Usuario

MODULOS = ("preliquidacion", "fletes")  # debe coincidir con app/modulos/__init__.py (test_registro_modulos)
ROLES_MODULO = ("operador", "gerente")


def modulos_de(usuario) -> dict[str, str]:
    """{'preliquidacion': 'operador', ...} a partir de usuario.modulos."""
    return {um.modulo: um.rol for um in (getattr(usuario, "modulos", None) or [])}


def tiene_permiso(usuario, modulo: str, *roles: str) -> bool:
    if getattr(usuario, "rol", None) == "admin":
        return True
    return modulos_de(usuario).get(modulo) in roles


def requiere_modulo(modulo: str, *roles: str):
    """Dependency de autorización: exige rol en el módulo (o admin). La
    restricción vive en el backend; el frontend solo esconde lo que no corresponde."""
    def dependencia(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if not tiene_permiso(usuario, modulo, *roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para esta operación",
            )
        return usuario
    return dependencia
