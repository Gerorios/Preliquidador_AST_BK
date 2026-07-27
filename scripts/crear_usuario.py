# Alta manual de usuarios (no hay ABM de usuarios en la app — decisión de la
# vista gerencial: los gerentes se crean a mano). Usa la misma config y hash
# bcrypt que el login.
#
# Uso:
#   python scripts/crear_usuario.py --nombre "Nombre Apellido" --email ger@laasturiana.com --password "..." [--rol gerente]
#
# Si el email ya existe, actualiza contraseña/rol/nombre en vez de duplicar.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionPropia  # noqa: E402
from app.models.models import Usuario, RolUsuario  # noqa: E402
from app.api.auth import pwd_context  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea o actualiza un usuario del preliquidador")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--rol", default=RolUsuario.GERENTE.value,
                        choices=[r.value for r in RolUsuario])
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
        db.commit()
        print(f"Usuario {accion}: {args.email} (rol {args.rol}, id {usuario.id})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
