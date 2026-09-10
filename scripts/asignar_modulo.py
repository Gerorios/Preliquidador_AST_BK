"""
Asigna, cambia o quita el rol de un usuario en un módulo.

    python scripts/asignar_modulo.py --email liq@x.com --modulo terceros --rol operador
    python scripts/asignar_modulo.py --email liq@x.com --modulo terceros --quitar
    python scripts/asignar_modulo.py --email liq@x.com --listar
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionPropia  # noqa: E402
from app.core.models import Usuario, UsuarioModulo  # noqa: E402
from app.core.permisos import MODULOS, ROLES_MODULO  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--modulo", choices=MODULOS)
    ap.add_argument("--rol", choices=ROLES_MODULO)
    ap.add_argument("--quitar", action="store_true")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    db = SessionPropia()
    try:
        u = db.query(Usuario).filter(Usuario.email == a.email).first()
        if not u:
            print(f"No existe el usuario {a.email}"); return 1
        if a.listar:
            print(f"{u.email} (rol {u.rol}):", {m.modulo: m.rol for m in u.modulos} or "sin módulos"); return 0
        if not a.modulo or (not a.rol and not a.quitar):
            ap.error("hace falta --modulo y (--rol o --quitar)")
        actual = next((m for m in u.modulos if m.modulo == a.modulo), None)
        if a.quitar:
            if actual: db.delete(actual); accion = "quitado"
            else: accion = "no tenía"
        elif actual:
            actual.rol = a.rol; accion = "actualizado"
        else:
            u.modulos.append(UsuarioModulo(modulo=a.modulo, rol=a.rol)); accion = "asignado"
        db.commit()
        print(f"{a.email}: {a.modulo} {accion}", f"({a.rol})" if a.rol else "")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
