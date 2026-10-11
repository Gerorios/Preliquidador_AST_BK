"""Scripts de consola de usuarios (ADR-0020, BK2 paso 2.6): la salida de
emergencia si el admin pierde el acceso a la pantalla.

- `scripts/crear_usuario.py` asigna roles por nombre con `--asignar-rol`
  (repetible) y usa `reemplazar_roles` de `roles_service`, que borra y hace
  flush antes de insertar: no choca contra la UNIQUE (usuario_id, rol_id).
- `scripts/asignar_rol.py` suma, quita y lista roles de una persona, y lista
  los roles que existen.
- Ninguno de los dos depende del esquema viejo por módulo, que sale en el 2.5.

Los scripts corren contra una SQLite en memoria: se reemplaza `SessionPropia`
dentro de cada script.
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import roles_service
from app.core.database import Base
from app.core.models import Rol, RolPermiso, Usuario
from scripts import asignar_rol, crear_usuario
from scripts.crear_usuario import reemplazar_roles

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture()
def fabrica(monkeypatch):
    """sessionmaker sobre una SQLite en memoria, puesto en lugar de
    `SessionPropia` en los dos scripts. Trae los roles Preliquidador y Gerente."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(crear_usuario, "SessionPropia", Session)
    monkeypatch.setattr(asignar_rol, "SessionPropia", Session)
    s = Session()
    s.add_all([
        Rol(nombre="Preliquidador", permisos=[
            RolPermiso(modulo="preliquidacion", pantalla="inicio", nivel="editar"),
            RolPermiso(modulo="preliquidacion", pantalla="conceptos", nivel="editar"),
        ]),
        Rol(nombre="Gerente", permisos=[
            RolPermiso(modulo="preliquidacion", pantalla="gerencial", nivel="ver"),
            RolPermiso(modulo="preliquidacion", pantalla="conceptos", nivel="ver"),
        ]),
    ])
    s.commit()
    s.close()
    return Session


def _usuario(Session, email="p@t.com", roles=(), rol="usuario"):
    s = Session()
    u = Usuario(nombre="Persona", email=email, password="x", rol=rol, activo=True,
                roles=[s.query(Rol).filter(Rol.nombre == n).one() for n in roles])
    s.add(u)
    s.commit()
    s.close()


def _roles_de(Session, email):
    s = Session()
    try:
        u = s.query(Usuario).filter(Usuario.email == email).first()
        return None if u is None else sorted(r.nombre for r in u.roles)
    finally:
        s.close()


# --- crear_usuario.py ---------------------------------------------------------

def test_crear_usuario_usa_reemplazar_roles_del_servicio():
    assert reemplazar_roles is roles_service.reemplazar_roles


def test_reemplazar_roles_no_choca_con_la_unique(fabrica):
    _usuario(fabrica, roles=["Preliquidador"])
    s = fabrica()
    u = s.query(Usuario).one()
    ids = [r.id for r in s.query(Rol).order_by(Rol.nombre)]
    assert reemplazar_roles(s, u, ids) is None
    s.commit()
    s.close()
    assert _roles_de(fabrica, "p@t.com") == ["Gerente", "Preliquidador"]


def test_parser_de_crear_usuario_acepta_asignar_rol_repetible():
    args = crear_usuario.construir_parser().parse_args([
        "--nombre", "N", "--email", "e@x.com", "--password", "p",
        "--asignar-rol", "Gerente", "--asignar-rol", "Preliquidador",
    ])
    assert args.asignar_rol == ["Gerente", "Preliquidador"]
    assert args.rol == "usuario"


def test_parser_de_crear_usuario_ya_no_acepta_modulo():
    with pytest.raises(SystemExit):
        crear_usuario.construir_parser().parse_args([
            "--nombre", "N", "--email", "e@x.com", "--password", "p",
            "--modulo", "preliquidacion:operador",
        ])


def test_crear_usuario_asigna_los_roles_por_nombre(fabrica):
    codigo = crear_usuario.main([
        "--nombre", "N", "--email", "n@x.com", "--password", "p",
        "--asignar-rol", "gerente", "--asignar-rol", "Preliquidador",
    ])
    assert codigo == 0
    assert _roles_de(fabrica, "n@x.com") == ["Gerente", "Preliquidador"]


def test_crear_usuario_con_un_rol_inexistente_no_escribe_nada(fabrica, capsys):
    codigo = crear_usuario.main([
        "--nombre", "N", "--email", "n@x.com", "--password", "p",
        "--asignar-rol", "Gerente", "--asignar-rol", "Inexistente",
    ])
    assert codigo != 0
    assert "Inexistente" in capsys.readouterr().err
    assert _roles_de(fabrica, "n@x.com") is None


def test_crear_usuario_existente_sin_asignar_rol_conserva_sus_roles(fabrica):
    _usuario(fabrica, email="n@x.com", roles=["Gerente"])
    codigo = crear_usuario.main([
        "--nombre", "N", "--email", "n@x.com", "--password", "p", "--rol", "admin",
    ])
    assert codigo == 0
    assert _roles_de(fabrica, "n@x.com") == ["Gerente"]


def test_crear_usuario_existente_con_asignar_rol_reemplaza_sus_roles(fabrica):
    _usuario(fabrica, email="n@x.com", roles=["Gerente"])
    codigo = crear_usuario.main([
        "--nombre", "N", "--email", "n@x.com", "--password", "p",
        "--asignar-rol", "Preliquidador",
    ])
    assert codigo == 0
    assert _roles_de(fabrica, "n@x.com") == ["Preliquidador"]


# --- asignar_rol.py -----------------------------------------------------------

def test_asignar_rol_suma_el_rol_sin_sacar_los_otros(fabrica):
    _usuario(fabrica, roles=["Gerente"])
    assert asignar_rol.main(["--email", "p@t.com", "--rol", "Preliquidador"]) == 0
    assert _roles_de(fabrica, "p@t.com") == ["Gerente", "Preliquidador"]


def test_asignar_rol_que_ya_tiene_no_cambia_nada(fabrica):
    _usuario(fabrica, roles=["Gerente"])
    assert asignar_rol.main(["--email", "p@t.com", "--rol", "Gerente"]) == 0
    assert _roles_de(fabrica, "p@t.com") == ["Gerente"]


def test_asignar_rol_quitar(fabrica):
    _usuario(fabrica, roles=["Gerente", "Preliquidador"])
    assert asignar_rol.main(["--email", "p@t.com", "--rol", "Gerente", "--quitar"]) == 0
    assert _roles_de(fabrica, "p@t.com") == ["Preliquidador"]


def test_asignar_rol_inexistente_sale_con_error_sin_escribir(fabrica, capsys):
    _usuario(fabrica, roles=["Gerente"])
    assert asignar_rol.main(["--email", "p@t.com", "--rol", "Inexistente"]) != 0
    assert "Inexistente" in capsys.readouterr().err
    assert _roles_de(fabrica, "p@t.com") == ["Gerente"]


def test_asignar_rol_a_un_email_inexistente_sale_con_error(fabrica, capsys):
    assert asignar_rol.main(["--email", "nadie@t.com", "--rol", "Gerente"]) != 0
    assert "nadie@t.com" in capsys.readouterr().err


def test_asignar_rol_listar_muestra_roles_y_permisos_efectivos(fabrica, capsys):
    _usuario(fabrica, roles=["Gerente", "Preliquidador"])
    assert asignar_rol.main(["--email", "p@t.com", "--listar"]) == 0
    salida = capsys.readouterr().out
    assert "Gerente" in salida and "Preliquidador" in salida
    # Editar (Preliquidador) le gana a Ver (Gerente) en Conceptos.
    assert "conceptos=editar" in salida
    assert "gerencial=ver" in salida


def test_asignar_rol_roles_lista_los_que_existen(fabrica, capsys):
    assert asignar_rol.main(["--roles"]) == 0
    salida = capsys.readouterr().out
    assert "Gerente" in salida and "Preliquidador" in salida
    assert "gerencial=ver" in salida


@pytest.mark.parametrize("argv", [
    [],                                              # sin acción
    ["--email", "p@t.com"],                          # sin acción
    ["--rol", "Gerente"],                            # sin --email
    ["--email", "p@t.com", "--quitar"],              # --quitar sin --rol
    ["--email", "p@t.com", "--listar", "--rol", "Gerente"],
])
def test_asignar_rol_rechaza_combinaciones_invalidas(argv):
    with pytest.raises(SystemExit) as exc:
        asignar_rol.main(argv)
    assert exc.value.code != 0


# --- Sin el esquema viejo -----------------------------------------------------

def test_los_scripts_no_usan_el_esquema_viejo():
    assert not (SCRIPTS / "asignar_modulo.py").exists()
    viejo = re.compile(r"\b(MODULOS|ROLES_MODULO|UsuarioModulo|reemplazar_modulos|"
                       r"requiere_modulo|modulos_de|asignar_modulo)\b"
                       r"|(?<!app)\.modulos\b")  # usuario.modulos, no el paquete app.modulos
    usos = [
        f"{archivo.name}:{n}: {linea.strip()}"
        for archivo in sorted(SCRIPTS.glob("*.py"))
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1)
        if viejo.search(linea)
    ]
    assert usos == []
