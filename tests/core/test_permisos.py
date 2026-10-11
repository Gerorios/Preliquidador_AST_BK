"""Permisos del núcleo que no dependen de los roles: el esquema por módulo
(ADR-0013) ya no existe y `requiere_admin` sigue igual. Los permisos por
pantalla (ADR-0020) se prueban en test_permisos_pantalla.py."""
from types import SimpleNamespace

from fastapi import HTTPException

import app.core.models as models
import app.core.permisos as permisos
from app.core.database import Base
from app.modulos import REGISTRO


def test_esquema_viejo_no_existe():
    # BK2 borra el esquema por módulo (operador/gerente en usuario_modulo) del
    # código, y core/003 borra la tabla de la base.
    for nombre in ("MODULOS", "ROLES_MODULO", "modulos_de", "tiene_permiso", "requiere_modulo"):
        assert not hasattr(permisos, nombre), f"app.core.permisos todavía exporta {nombre}"
    assert not hasattr(models, "UsuarioModulo")
    assert not hasattr(models.Usuario, "modulos")
    assert "usuario_modulo" not in Base.metadata.tables
    for m in REGISTRO:
        assert not hasattr(m, "etiquetas_rol"), f"{m.clave} todavía declara etiquetas_rol"
        assert "etiquetas_rol" not in m.publico()


def test_requiere_admin_deja_pasar_al_admin_y_rechaza_al_resto():
    dependencia = permisos.requiere_admin()

    admin = SimpleNamespace(rol="admin")
    assert dependencia(usuario=admin) is admin

    for rol in ("usuario", None):
        comun = SimpleNamespace(rol=rol)
        try:
            dependencia(usuario=comun)
        except HTTPException as e:
            assert e.status_code == 403
        else:
            raise AssertionError(f"rol {rol!r} no debería pasar requiere_admin")
