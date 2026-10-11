# Alta manual de usuarios por consola: la alternativa a Administración y la
# salida de emergencia si el admin pierde su propio acceso. Usa la misma config
# y hash bcrypt que el login.
#
# Uso:
#   python scripts/crear_usuario.py --nombre "Nombre Apellido" --email liq@x.com --password "..." \
#       --asignar-rol "Preliquidador"
#   python scripts/crear_usuario.py --nombre "Nombre Apellido" --email admin@x.com --password "..." --rol admin
#
# Si el email ya existe, actualiza contraseña/rol/nombre en vez de duplicar.
# Con --asignar-rol (repetible, el nombre de un rol armable, ADR-0020) reemplaza
# los roles del usuario por los pasados. Si no se pasa --asignar-rol y el
# usuario ya existe, sus roles no se tocan. Si algún rol no existe, no escribe
# nada. Para sumar o quitar un rol sin tocar los otros: scripts/asignar_rol.py.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionPropia  # noqa: E402
from app.core.models import Rol, Usuario, RolUsuario  # noqa: E402
from app.core.auth import pwd_context  # noqa: E402
from app.core.roles_service import reemplazar_roles, rol_con_el_nombre  # noqa: E402


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crea o actualiza un usuario del Sistema")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--rol", default=RolUsuario.USUARIO.value,
                        choices=["admin", "usuario"],
                        help="marca global: admin ve todo sin necesitar roles")
    parser.add_argument("--asignar-rol", action="append", default=[], metavar="NOMBRE",
                        help='repetible, p. ej. --asignar-rol "Preliquidador" '
                             "(los que existen: scripts/asignar_rol.py --roles)")
    return parser


def _roles_por_nombre(db, nombres: list[str]) -> tuple[list[Rol], list[str]]:
    """(roles encontrados, nombres que no existen). Compara como la base: sin
    distinguir mayúsculas ni acentos."""
    roles, faltan = [], []
    for nombre in nombres:
        rol = rol_con_el_nombre(db, nombre)
        if rol is None:
            faltan.append(nombre)
        else:
            roles.append(rol)
    return roles, faltan


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    db = SessionPropia()
    try:
        roles, faltan = _roles_por_nombre(db, args.asignar_rol)
        if faltan:
            existentes = ", ".join(r.nombre for r in db.query(Rol).order_by(Rol.nombre)) or "ninguno"
            print(
                f"No existe el rol {', '.join(repr(n) for n in faltan)}. "
                f"Roles: {existentes}. No se escribió nada.",
                file=sys.stderr,
            )
            return 1

        hash_ = pwd_context.hash(args.password)
        usuario = db.query(Usuario).filter(Usuario.email == args.email).first()
        if usuario:
            usuario.nombre = args.nombre
            usuario.password = hash_
            usuario.rol = args.rol
            usuario.activo = True
            accion = "actualizado"
        else:
            usuario = Usuario(
                nombre=args.nombre, email=args.email,
                password=hash_, rol=args.rol, activo=True,
            )
            db.add(usuario)
            accion = "creado"

        if args.asignar_rol:
            motivo = reemplazar_roles(db, usuario, [r.id for r in roles])
            if motivo:
                db.rollback()
                print(f"{motivo} No se escribió nada.", file=sys.stderr)
                return 1

        db.commit()

        roles_txt = ", ".join(r.nombre for r in usuario.roles) or "ninguno"
        print(
            f"Usuario {accion}: {args.email} (rol {args.rol}; "
            f"roles: {roles_txt}, id {usuario.id})"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
