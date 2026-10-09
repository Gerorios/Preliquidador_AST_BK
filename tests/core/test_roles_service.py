"""Servicio de roles armables (ADR-0020): alta, cambio y borrado de roles, y
reemplazo de los roles de una persona.

Los textos de los motivos son los mismos que muestra el editor de roles del
front (`src/core/administracion/roles.js`, `motivoParaNoGuardar` y
`motivoParaNoBorrar`), y las validaciones van en el mismo orden.

El catálogo se arma acá con `ModuloInfo` y `Pantalla` del núcleo, igual que el
que llega por `app.state` (sólo módulos activos): el núcleo no importa módulos.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import pwd_context
from app.core.database import Base
from app.core.models import Rol, RolPermiso, Usuario, UsuarioRol
from app.core.modulos import ModuloInfo, Pantalla
from app.core.roles_service import (
    actualizar_rol, borrar_rol, crear_rol, motivo_para_no_guardar, personas_con_rol,
    reemplazar_roles, rol_con_el_nombre,
)

CATALOGO = (
    ModuloInfo(
        clave="preliquidacion", nombre="Preliquidación", descripcion="", activo=True,
        pantallas=(
            Pantalla("inicio", "Inicio"),
            Pantalla("revision", "Revisión", requiere=("inicio",)),
            Pantalla("verificacion", "Verificación"),
            Pantalla("mantenimiento", "Mantenimiento"),
            Pantalla("conceptos", "Conceptos"),
            Pantalla("gerencial", "Vista gerencial", editable=False),
        ),
    ),
    ModuloInfo(
        clave="terceros", nombre="Liquidación Terceros", descripcion="", activo=True,
        pantallas=(
            Pantalla("inicio", "Inicio"),
            Pantalla("quincena", "Quincena"),
            Pantalla("verificaciones", "Verificaciones", editable=False),
        ),
    ),
)

CONCEPTOS_VER = {"preliquidacion": {"conceptos": "ver"}}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _usuario(db, nombre="Ana", email=None, activo=True):
    u = Usuario(nombre=nombre, email=email or f"{nombre.lower()}@t.com",
                password=pwd_context.hash("x"), rol="usuario", activo=activo)
    db.add(u)
    db.commit()
    return u


def _crear(db, nombre, permisos):
    rol, motivo = crear_rol(db, nombre, permisos, CATALOGO)
    assert motivo is None, motivo
    return rol


def _permisos(rol) -> dict:
    salida: dict = {}
    for p in rol.permisos:
        salida.setdefault(p.modulo, {})[p.pantalla] = p.nivel
    return salida


def _motivo(db, nombre="Consulta", permisos=None, rol_id=None):
    return motivo_para_no_guardar(
        db, nombre, CONCEPTOS_VER if permisos is None else permisos, CATALOGO, rol_id
    )


# ─── Alta ────────────────────────────────────────────────────────────────────

def test_crea_el_rol_con_sus_permisos_y_el_nombre_recortado(db):
    rol, motivo = crear_rol(db, "  Consulta  ", {
        "preliquidacion": {"inicio": "editar", "revision": "ver", "gerencial": "ver"},
        "terceros": {"quincena": "ver"},
    }, CATALOGO)
    assert motivo is None
    assert rol.id is not None
    assert rol.nombre == "Consulta"
    db.expire_all()
    guardado = db.query(Rol).filter(Rol.id == rol.id).one()
    assert _permisos(guardado) == {
        "preliquidacion": {"inicio": "editar", "revision": "ver", "gerencial": "ver"},
        "terceros": {"quincena": "ver"},
    }


def test_un_rechazo_no_crea_nada(db):
    rol, motivo = crear_rol(db, "", CONCEPTOS_VER, CATALOGO)
    assert rol is None
    assert motivo == "El rol necesita un nombre."
    assert db.query(Rol).count() == 0


def test_las_pantallas_sin_nivel_no_se_guardan(db):
    rol = _crear(db, "Consulta", {
        "preliquidacion": {"conceptos": "ver", "inicio": None, "verificacion": "", "mantenimiento": "sin"},
        "terceros": {},
    })
    assert _permisos(rol) == {"preliquidacion": {"conceptos": "ver"}}


# ─── Validaciones (mismo orden y textos que el front) ────────────────────────

def test_nombre_vacio(db):
    for nombre in ("", "   ", None):
        assert _motivo(db, nombre=nombre) == "El rol necesita un nombre."


def test_nombre_de_hasta_60_caracteres_sin_contar_los_bordes(db):
    assert _motivo(db, nombre="a" * 60) is None
    assert _motivo(db, nombre=f"  {'a' * 60}  ") is None
    assert _motivo(db, nombre="ñ" * 60) is None
    assert _motivo(db, nombre="a" * 61) == "El nombre puede tener hasta 60 caracteres."


def test_gerente_gerente_y_gerente_con_acento_son_el_mismo_nombre(db):
    _crear(db, "Gerente", {"preliquidacion": {"gerencial": "ver"}})
    esperado = 'Ya hay un rol que se llama "Gerente".'
    assert _motivo(db, nombre="Gerente") == esperado
    assert _motivo(db, nombre="  gerente ") == esperado
    assert _motivo(db, nombre="Gérente") == esperado
    assert _motivo(db, nombre="GERÉNTE") == esperado
    rol, motivo = crear_rol(db, "gerente", CONCEPTOS_VER, CATALOGO)
    assert (rol, motivo) == (None, esperado)


def test_el_nombre_repetido_nombra_al_rol_existente_tal_como_esta(db):
    _crear(db, "Revisión", {"preliquidacion": {"inicio": "ver", "revision": "ver"}})
    assert _motivo(db, nombre="revision") == 'Ya hay un rol que se llama "Revisión".'


def test_rol_con_el_nombre_ignora_mayusculas_acentos_y_al_rol_que_se_edita(db):
    gerente = _crear(db, "Gerente", {"preliquidacion": {"gerencial": "ver"}})
    assert rol_con_el_nombre(db, " gérente ") is gerente
    assert rol_con_el_nombre(db, "gerente", excluir_id=gerente.id) is None
    assert rol_con_el_nombre(db, "Otro") is None


def test_al_editar_su_propio_nombre_no_cuenta_como_repetido(db):
    gerente = _crear(db, "Gerente", {"preliquidacion": {"gerencial": "ver"}})
    otro = _crear(db, "Otro", CONCEPTOS_VER)
    assert _motivo(db, nombre="gerente", rol_id=gerente.id) is None
    assert _motivo(db, nombre="Gerente", rol_id=otro.id) == 'Ya hay un rol que se llama "Gerente".'


def test_rol_sin_pantallas(db):
    esperado = "El rol tiene que dar acceso al menos a una pantalla."
    assert _motivo(db, permisos={}) == esperado
    assert _motivo(db, permisos={"preliquidacion": {"inicio": None}, "terceros": {}}) == esperado


def test_modulo_inexistente_o_inactivo(db):
    assert _motivo(db, permisos={"facturacion": {"inicio": "ver"}}) == \
        'El módulo "facturacion" no existe o no está activo.'


def test_pantalla_inexistente(db):
    assert _motivo(db, permisos={"preliquidacion": {"tarifario": "ver"}}) == \
        'Preliquidación no tiene la pantalla "tarifario".'


def test_nivel_desconocido(db):
    assert _motivo(db, permisos={"preliquidacion": {"conceptos": "operador"}}) == \
        'Conceptos tiene un nivel desconocido: "operador".'


def test_editar_en_gerencial(db):
    assert _motivo(db, permisos={"preliquidacion": {"gerencial": "editar"}}) == \
        "Vista gerencial sólo admite Ver."
    assert _motivo(db, permisos={"terceros": {"verificaciones": "editar"}}) == \
        "Verificaciones sólo admite Ver."


def test_revision_necesita_al_menos_ver_en_inicio(db):
    esperado = "Revisión necesita al menos Ver en Inicio."
    assert _motivo(db, permisos={"preliquidacion": {"revision": "editar"}}) == esperado
    assert _motivo(db, permisos={"preliquidacion": {"revision": "ver", "inicio": None}}) == esperado
    assert _motivo(db, permisos={"preliquidacion": {"revision": "editar", "inicio": "ver"}}) is None
    assert _motivo(db, permisos={"preliquidacion": {"inicio": "ver"}}) is None


def test_la_regla_requiere_es_generica_y_nombra_todas_las_que_faltan(db):
    catalogo = (ModuloInfo(
        clave="facturacion", nombre="Facturación", descripcion="", activo=True,
        pantallas=(
            Pantalla("inicio", "Inicio"),
            Pantalla("clientes", "Clientes"),
            Pantalla("facturas", "Facturas", requiere=("inicio", "clientes")),
        ),
    ),)
    assert motivo_para_no_guardar(db, "X", {"facturacion": {"facturas": "ver"}}, catalogo) == \
        "Facturas necesita al menos Ver en Inicio y Clientes."
    assert motivo_para_no_guardar(
        db, "X", {"facturacion": {"facturas": "ver", "clientes": "ver"}}, catalogo
    ) == "Facturas necesita al menos Ver en Inicio."


def test_el_nombre_se_valida_antes_que_los_permisos(db):
    assert _motivo(db, nombre="", permisos={}) == "El rol necesita un nombre."
    _crear(db, "Gerente", {"preliquidacion": {"gerencial": "ver"}})
    assert _motivo(db, nombre="gerente", permisos={"facturacion": {"inicio": "ver"}}) == \
        'Ya hay un rol que se llama "Gerente".'


# ─── Cambio ──────────────────────────────────────────────────────────────────

def test_actualizar_dejando_la_misma_pantalla_no_choca_contra_la_unique(db):
    rol = _crear(db, "Consulta", {"preliquidacion": {"inicio": "ver", "conceptos": "ver"}})
    motivo = actualizar_rol(db, rol, "Consulta", {
        "preliquidacion": {"inicio": "editar", "conceptos": "ver", "verificacion": "ver"},
    }, CATALOGO)
    assert motivo is None
    db.expire_all()
    guardado = db.query(Rol).filter(Rol.id == rol.id).one()
    assert _permisos(guardado) == {
        "preliquidacion": {"inicio": "editar", "conceptos": "ver", "verificacion": "ver"},
    }
    assert db.query(RolPermiso).count() == 3


def test_actualizar_cambia_el_nombre_y_saca_las_pantallas_que_no_vienen(db):
    rol = _crear(db, "Consulta", {
        "preliquidacion": {"inicio": "ver", "conceptos": "ver"},
        "terceros": {"quincena": "ver"},
    })
    assert actualizar_rol(db, rol, "  Lectura ", {"preliquidacion": {"conceptos": "editar"}}, CATALOGO) is None
    db.expire_all()
    guardado = db.query(Rol).filter(Rol.id == rol.id).one()
    assert guardado.nombre == "Lectura"
    assert _permisos(guardado) == {"preliquidacion": {"conceptos": "editar"}}


def test_actualizar_conserva_los_permisos_de_un_modulo_inactivo(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    # Un módulo que no está en el catálogo (inactivo hoy): sólo se puede haber
    # cargado cuando estaba activo, así que se inserta directo.
    db.add(RolPermiso(rol_id=rol.id, modulo="facturacion", pantalla="inicio", nivel="editar"))
    db.commit()
    db.expire_all()
    rol = db.query(Rol).filter(Rol.id == rol.id).one()

    assert actualizar_rol(db, rol, "Consulta", {"terceros": {"quincena": "ver"}}, CATALOGO) is None
    db.expire_all()
    guardado = db.query(Rol).filter(Rol.id == rol.id).one()
    assert _permisos(guardado) == {
        "facturacion": {"inicio": "editar"},
        "terceros": {"quincena": "ver"},
    }


def test_actualizar_rechazado_no_cambia_nada(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    _crear(db, "Gerente", {"preliquidacion": {"gerencial": "ver"}})
    assert actualizar_rol(db, rol, "gerente", CONCEPTOS_VER, CATALOGO) == \
        'Ya hay un rol que se llama "Gerente".'
    assert actualizar_rol(db, rol, "Consulta", {"preliquidacion": {"gerencial": "editar"}}, CATALOGO) == \
        "Vista gerencial sólo admite Ver."
    db.expire_all()
    guardado = db.query(Rol).filter(Rol.id == rol.id).one()
    assert guardado.nombre == "Consulta"
    assert _permisos(guardado) == CONCEPTOS_VER


# ─── Borrado ─────────────────────────────────────────────────────────────────

def test_borrar_un_rol_que_nadie_tiene(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    assert borrar_rol(db, rol) is None
    assert db.query(Rol).count() == 0
    assert db.query(RolPermiso).count() == 0


def test_borrar_un_rol_en_uso_dice_cuantas_y_quienes_marcando_las_inactivas(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    beto = _usuario(db, "Beto", activo=False)
    ana = _usuario(db, "Ana")
    assert reemplazar_roles(db, beto, [rol.id]) is None
    assert reemplazar_roles(db, ana, [rol.id]) is None
    db.commit()

    assert borrar_rol(db, rol) == \
        "Lo tienen 2 personas: Ana y Beto (inactiva). Sacáselo primero para poder borrarlo."
    assert db.query(Rol).count() == 1
    assert [p.nombre for p in personas_con_rol(db, rol)] == ["Ana", "Beto"]


def test_borrar_un_rol_que_tiene_una_sola_persona_va_en_singular(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    ana = _usuario(db, "Ana")
    reemplazar_roles(db, ana, [rol.id])
    db.commit()
    assert borrar_rol(db, rol) == "Lo tiene 1 persona: Ana. Sacáselo primero para poder borrarlo."


def test_borrar_un_rol_con_tres_personas_enumera_con_comas(db):
    rol = _crear(db, "Consulta", CONCEPTOS_VER)
    for nombre in ("Carla", "Ana", "Beto"):
        reemplazar_roles(db, _usuario(db, nombre), [rol.id])
    db.commit()
    assert borrar_rol(db, rol) == \
        "Lo tienen 3 personas: Ana, Beto y Carla. Sacáselo primero para poder borrarlo."


# ─── Roles de una persona ────────────────────────────────────────────────────

def test_reemplazar_roles_de_una_persona(db):
    a = _crear(db, "A", CONCEPTOS_VER)
    b = _crear(db, "B", {"preliquidacion": {"gerencial": "ver"}})
    c = _crear(db, "C", {"terceros": {"quincena": "ver"}})
    ana = _usuario(db, "Ana")

    assert reemplazar_roles(db, ana, [a.id, b.id]) is None
    db.commit()
    # Queda B (sin tocar su fila), sale A y entra C.
    assert reemplazar_roles(db, ana, [b.id, c.id]) is None
    db.commit()
    db.expire_all()
    assert sorted(r.nombre for r in db.query(Usuario).filter(Usuario.id == ana.id).one().roles) == ["B", "C"]
    assert db.query(UsuarioRol).count() == 2

    assert reemplazar_roles(db, ana, []) is None
    db.commit()
    assert db.query(UsuarioRol).count() == 0


def test_reemplazar_roles_con_un_id_repetido_no_choca_contra_la_unique(db):
    a = _crear(db, "A", CONCEPTOS_VER)
    ana = _usuario(db, "Ana")
    assert reemplazar_roles(db, ana, [a.id, a.id]) is None
    db.commit()
    assert db.query(UsuarioRol).count() == 1


def test_reemplazar_roles_con_un_id_inexistente_devuelve_motivo_y_no_cambia_nada(db):
    a = _crear(db, "A", CONCEPTOS_VER)
    ana = _usuario(db, "Ana")
    reemplazar_roles(db, ana, [a.id])
    db.commit()

    motivo = reemplazar_roles(db, ana, [a.id, 9999])
    assert motivo == "No existe el rol con id 9999."
    db.commit()
    db.expire_all()
    assert [r.nombre for r in db.query(Usuario).filter(Usuario.id == ana.id).one().roles] == ["A"]
