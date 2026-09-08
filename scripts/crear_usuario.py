# Alta manual de usuarios (no hay ABM de usuarios en la app — decisión de la
# vista gerencial: los gerentes se crean a mano). Usa la misma config y hash
# bcrypt que el login.
#
# Uso:
#   python scripts/crear_usuario.py --nombre "Nombre Apellido" --email liq@x.com --password "..." \
#       --modulo preliquidacion:operador
#   python scripts/crear_usuario.py --nombre "Nombre Apellido" --email admin@x.com --password "..." --rol admin
#
# Si el email ya existe, actualiza contraseña/rol/nombre en vez de duplicar.
# Con --modulo (repetible, formato modulo:rol) reemplaza los módulos del
# usuario por los pasados. Si no se pasa --modulo y el usuario ya existe, sus
# módulos no se tocan.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionPropia  # noqa: E402
from app.core.models import Usuario, UsuarioModulo, RolUsuario  # noqa: E402
from app.core.auth import pwd_context  # noqa: E402
from app.core.permisos import MODULOS, ROLES_MODULO  # noqa: E402


def reemplazar_modulos(db, usuario: Usuario, pares: list[tuple[str, str]]) -> None:
    """Reemplaza los módulos del usuario por `pares` (modulo, rol).

    Borra los módulos viejos y hace flush antes de asignar los nuevos: si se
    reasigna `usuario.modulos = [...]` directamente, SQLAlchemy intenta
    insertar las filas nuevas antes de borrar las huérfanas y choca contra la
    UNIQUE (usuario_id, modulo) con un IntegrityError.
    """
    for m in list(usuario.modulos):
        db.delete(m)
    db.flush()
    usuario.modulos = [UsuarioModulo(modulo=m, rol=r) for m, r in pares]


def _parse_modulo(valor: str) -> tuple[str, str]:
    if ":" not in valor:
        raise argparse.ArgumentTypeError(
            f"--modulo debe tener formato modulo:rol (recibido {valor!r})"
        )
    modulo, rol = valor.split(":", 1)
    if modulo not in MODULOS:
        raise argparse.ArgumentTypeError(
            f"módulo inválido {modulo!r} (válidos: {', '.join(MODULOS)})"
        )
    if rol not in ROLES_MODULO:
        raise argparse.ArgumentTypeError(
            f"rol inválido {rol!r} para el módulo {modulo!r} (válidos: {', '.join(ROLES_MODULO)})"
        )
    return modulo, rol


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea o actualiza un usuario del preliquidador")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--rol", default=RolUsuario.USUARIO.value,
                        choices=["admin", "usuario"])
    parser.add_argument("--modulo", action="append", type=_parse_modulo, default=[],
                        metavar="modulo:rol",
                        help="repetible, p. ej. --modulo preliquidacion:operador")
    args = parser.parse_args()

    db = SessionPropia()
    try:
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

        if args.modulo:
            reemplazar_modulos(db, usuario, args.modulo)

        db.commit()

        modulos_txt = ", ".join(f"{m.modulo}={m.rol}" for m in usuario.modulos) or "ninguno"
        print(
            f"Usuario {accion}: {args.email} (rol {args.rol}; "
            f"módulos: {modulos_txt}, id {usuario.id})"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
