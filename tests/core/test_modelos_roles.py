"""Modelos de roles armables (ADR-0020): `Rol`, `RolPermiso`, `UsuarioRol` y
`Usuario.roles`.

Las tres UNIQUE son las del `CREATE TABLE` de `core/002`. El test del cache
cubre el riesgo 4 del plan: sin `expunge` en la cascada de `Usuario.roles`, los
`Rol` del usuario cacheado quedan en la sesión de la request, un `commit` los
vence y al cerrar la sesión quedan desligados; la request siguiente que lea sus
permisos revienta con `DetachedInstanceError`."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import crear_token, get_usuario_actual, invalidar_cache_usuarios, pwd_context
from app.core.database import Base
from app.core.models import Rol, RolPermiso, Usuario, UsuarioRol


@pytest.fixture()
def fabrica():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def db(fabrica):
    s = fabrica()
    yield s
    s.close()


def _usuario(db, email="liq@t.com"):
    u = Usuario(nombre="Liq", email=email, password=pwd_context.hash("x"), rol="usuario", activo=True)
    db.add(u)
    db.commit()
    return u


def test_nombre_de_rol_es_unico(db):
    db.add(Rol(nombre="Preliquidador"))
    db.commit()
    db.add(Rol(nombre="Preliquidador"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_permiso_es_unico_por_rol_modulo_y_pantalla(db):
    rol = Rol(nombre="Preliquidador")
    db.add(rol)
    db.commit()
    db.add(RolPermiso(rol_id=rol.id, modulo="preliquidacion", pantalla="inicio", nivel="ver"))
    db.commit()
    db.add(RolPermiso(rol_id=rol.id, modulo="preliquidacion", pantalla="inicio", nivel="editar"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_usuario_rol_es_unico_por_usuario_y_rol(db):
    u = _usuario(db)
    rol = Rol(nombre="Preliquidador")
    db.add(rol)
    db.commit()
    db.add(UsuarioRol(usuario_id=u.id, rol_id=rol.id))
    db.commit()
    db.add(UsuarioRol(usuario_id=u.id, rol_id=rol.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_usuario_roles_carga_los_roles_con_sus_permisos(db):
    u = _usuario(db)
    rol = Rol(nombre="Gerente", permisos=[
        RolPermiso(modulo="preliquidacion", pantalla="gerencial", nivel="ver"),
        RolPermiso(modulo="preliquidacion", pantalla="conceptos", nivel="editar"),
    ])
    u.roles.append(rol)
    db.commit()
    db.expire_all()

    u = db.query(Usuario).one()
    assert [r.nombre for r in u.roles] == ["Gerente"]
    assert {(p.pantalla, p.nivel) for p in u.roles[0].permisos} == {
        ("gerencial", "ver"), ("conceptos", "editar"),
    }
    assert db.query(UsuarioRol).count() == 1


def test_usuario_del_cache_sobrevive_a_un_commit_en_la_misma_request(fabrica):
    preparar = fabrica()
    u = _usuario(preparar)
    u.roles.append(Rol(nombre="Preliquidador", permisos=[
        RolPermiso(modulo="preliquidacion", pantalla="inicio", nivel="editar"),
    ]))
    preparar.commit()
    usuario_id = u.id
    preparar.close()

    invalidar_cache_usuarios()
    try:
        # Una request: carga a la persona (queda en el cache), escribe otra cosa
        # en la misma sesión y la cierra, como get_db_propia al terminar.
        request = fabrica()
        usuario = get_usuario_actual(token=crear_token({"sub": usuario_id}), db=request)
        request.add(Rol(nombre="Otro"))
        request.commit()
        request.close()

        # La request siguiente usa el objeto del cache.
        assert usuario.roles[0].permisos[0].nivel == "editar"
    finally:
        invalidar_cache_usuarios()
