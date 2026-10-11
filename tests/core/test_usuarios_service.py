"""Alta de usuarios desde el padrón, reset de contraseña y las tres
protecciones que impiden quedarse afuera del sistema (PR 5 etapa 0)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context, verificar_password
from app.core.database import Base
from app.core.identidad import email_de_cuil
from app.core.models import Rol, Usuario
from app.core.roles_service import reemplazar_roles
from app.core.usuarios_service import (
    crear_usuarios_lote, resetear_password, validar_cambio,
)

CUIL_A = "20111111119"
CUIL_B = "27222222224"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _rol(db, nombre):
    rol = Rol(nombre=nombre)
    db.add(rol); db.commit()
    return rol


def _admin(db, email="adm@t.com", activo=True):
    u = Usuario(nombre="Adm", email=email, password=pwd_context.hash("x"), rol="admin", activo=activo)
    db.add(u); db.commit()
    return u


def test_crea_los_usuarios_del_lote_con_email_sintetico_y_password_igual_al_cuil(db):
    terceros, gerente = _rol(db, "Liquidador de terceros"), _rol(db, "Gerente")
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        roles=[terceros.id, gerente.id],
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_A, CUIL_B]
    assert r["omitidos"] == []

    u = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one()
    assert u.nombre == "GOMEZ, JUAN"
    assert u.rol == "usuario"
    assert u.activo is True
    assert verificar_password(CUIL_A, u.password), "la contraseña inicial es el CUIL"
    assert sorted(rol.nombre for rol in u.roles) == ["Gerente", "Liquidador de terceros"]
    otra = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_B)).one()
    assert sorted(rol.nombre for rol in otra.roles) == ["Gerente", "Liquidador de terceros"]


def test_omite_a_quien_ya_tiene_usuario_y_crea_al_resto(db):
    crear_usuarios_lote(db, [{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"}], "usuario", [])
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        roles=[],
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_B]
    assert r["omitidos"] == [{"cuil": CUIL_A, "motivo": "ya tiene usuario"}]


def test_omite_cuil_invalido_sin_abortar_el_lote(db):
    r = crear_usuarios_lote(
        db,
        personas=[{"cuil": "123", "apellido_nombre": "SIN CUIL"},
                  {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
        rol_global="usuario",
        roles=[],
    )
    assert [c["cuil"] for c in r["creados"]] == [CUIL_B]
    assert r["omitidos"] == [{"cuil": "123", "motivo": "CUIL inválido"}]


def test_un_rol_inexistente_rechaza_el_lote_sin_crear_a_nadie(db):
    """Mismo criterio y texto que reemplazar_roles (PUT /usuarios/{id}/roles)."""
    gerente = _rol(db, "Gerente")
    with pytest.raises(ValueError, match=r"^No existe el rol con id 999\.$"):
        crear_usuarios_lote(
            db,
            personas=[{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"},
                      {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA"}],
            rol_global="usuario",
            roles=[gerente.id, 999],
        )
    # Sin rollback: el rechazo es antes de agregar a nadie a la sesión.
    assert db.query(Usuario).count() == 0


def test_reemplazar_roles_no_choca_contra_la_unique(db):
    u = _admin(db)
    gerente, auditor = _rol(db, "Gerente"), _rol(db, "Auditor")
    assert reemplazar_roles(db, u, [gerente.id]) is None
    db.commit()
    # Repite el que ya tenía: (usuario_id, rol_id) no puede insertarse dos veces.
    assert reemplazar_roles(db, u, [gerente.id, auditor.id]) is None
    db.commit()
    db.expire_all()
    assert sorted(r.nombre for r in u.roles) == ["Auditor", "Gerente"]


def test_resetear_password_vuelve_al_cuil(db):
    crear_usuarios_lote(db, [{"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN"}], "usuario", [])
    u = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one()
    u.password = pwd_context.hash("otra-cosa"); db.commit()

    nueva = resetear_password(db, u)
    assert nueva == CUIL_A
    assert verificar_password(CUIL_A, u.password)


def test_resetear_password_de_mail_real_exige_password_explicita(db):
    u = _admin(db, email="liq@asturiana.com")
    with pytest.raises(ValueError):
        resetear_password(db, u)
    assert resetear_password(db, u, "temporal-123") == "temporal-123"
    assert verificar_password("temporal-123", u.password)


def test_proteccion_no_puede_desactivarse_a_si_mismo(db):
    a = _admin(db)
    assert validar_cambio(db, a, a, activo=False, rol=None) is not None


def test_proteccion_no_puede_quitarse_el_rol_admin(db):
    a = _admin(db)
    assert validar_cambio(db, a, a, activo=None, rol="usuario") is not None


def test_proteccion_no_deja_el_sistema_sin_admin_activo(db):
    a = _admin(db, email="a@t.com")
    b = _admin(db, email="b@t.com")
    # Con dos admins activos, degradar a uno está permitido.
    assert validar_cambio(db, a, b, activo=None, rol="usuario") is None
    b.rol = "usuario"; db.commit()
    # Ahora 'a' es el único admin activo: nadie puede degradarlo ni desactivarlo.
    assert validar_cambio(db, b, a, activo=False, rol=None) is not None
    assert validar_cambio(db, b, a, activo=None, rol="usuario") is not None


def test_cambios_inocuos_estan_permitidos(db):
    a = _admin(db, email="a@t.com")
    _admin(db, email="b@t.com")
    assert validar_cambio(db, a, a, activo=None, rol="admin") is None
    assert validar_cambio(db, a, a, activo=True, rol=None) is None
