"""
Suma, quita o lista los roles de una persona, y lista los roles que existen
(roles armables, ADR-0020). Es la alternativa de consola a Administración y la
salida de emergencia si el admin pierde su propio acceso.

    python scripts/asignar_rol.py --email liq@x.com --rol "Preliquidador"
    python scripts/asignar_rol.py --email liq@x.com --rol "Preliquidador" --quitar
    python scripts/asignar_rol.py --email liq@x.com --listar
    python scripts/asignar_rol.py --roles

--rol suma ese rol sin tocar los otros que la persona ya tiene; con --quitar,
lo saca. El nombre se compara como en la base, sin distinguir mayúsculas ni
acentos. Si el rol o la persona no existen, no escribe nada y sale con 1.
--listar muestra sus roles y sus permisos efectivos (el máximo entre sus roles;
Editar incluye Ver). Los roles se arman en Administración, no acá.

El backend guarda a cada persona en un cache de 60 segundos: un cambio hecho
desde acá puede tardar hasta un minuto en valer en la API.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionPropia  # noqa: E402
from app.core.models import Rol, Usuario  # noqa: E402
from app.core.permisos import permisos_de  # noqa: E402
from app.core.roles_service import (  # noqa: E402
    personas_con_rol, reemplazar_roles, rol_con_el_nombre,
)


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", help="la persona (obligatorio salvo con --roles)")
    accion = ap.add_mutually_exclusive_group()
    accion.add_argument("--rol", metavar="NOMBRE", help="rol a sumar (o a sacar, con --quitar)")
    accion.add_argument("--listar", action="store_true",
                        help="roles y permisos efectivos de la persona")
    accion.add_argument("--roles", action="store_true",
                        help="los roles que existen, con sus permisos")
    ap.add_argument("--quitar", action="store_true", help="saca el rol de --rol")
    return ap


def _texto_permisos(permisos: dict[str, dict[str, str]]) -> str:
    """'preliquidacion: conceptos=editar, gerencial=ver; terceros: ...'."""
    return "; ".join(
        f"{modulo}: " + ", ".join(f"{p}={n}" for p, n in sorted(pantallas.items()))
        for modulo, pantallas in sorted(permisos.items())
    ) or "ninguno"


def _permisos_del_rol(rol: Rol) -> dict[str, dict[str, str]]:
    permisos: dict[str, dict[str, str]] = {}
    for p in rol.permisos:
        permisos.setdefault(p.modulo, {})[p.pantalla] = p.nivel
    return permisos


def _listar_roles(db) -> int:
    roles = db.query(Rol).order_by(Rol.nombre).all()
    if not roles:
        print("No hay roles. Se arman en Administración.")
    for rol in roles:
        cuantas = len(personas_con_rol(db, rol))
        personas = "1 persona" if cuantas == 1 else f"{cuantas} personas"
        print(f"{rol.nombre} ({personas}): {_texto_permisos(_permisos_del_rol(rol))}")
    return 0


def _listar_persona(u: Usuario) -> int:
    roles = ", ".join(r.nombre for r in u.roles) or "ninguno"
    estado = "activo" if u.activo else "inactivo"
    print(f"{u.email} ({u.nombre}; rol {u.rol}; {estado})")
    print(f"  Roles: {roles}")
    if u.rol == "admin":
        print("  Permisos efectivos: todos (es administrador)")
    else:
        print(f"  Permisos efectivos: {_texto_permisos(permisos_de(u))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = construir_parser()
    a = ap.parse_args(argv)
    if a.roles:
        if a.email or a.quitar:
            ap.error("--roles no se combina con --email ni --quitar")
    elif not a.email:
        ap.error("hace falta --email (o --roles)")
    elif a.quitar and not a.rol:
        ap.error("--quitar necesita --rol")
    elif not a.rol and not a.listar:
        ap.error("hace falta --rol, --listar o --roles")

    db = SessionPropia()
    try:
        if a.roles:
            return _listar_roles(db)

        u = db.query(Usuario).filter(Usuario.email == a.email).first()
        if not u:
            print(f"No existe el usuario {a.email}. No se escribió nada.", file=sys.stderr)
            return 1
        if a.listar:
            return _listar_persona(u)

        rol = rol_con_el_nombre(db, a.rol)
        if rol is None:
            existentes = ", ".join(r.nombre for r in db.query(Rol).order_by(Rol.nombre)) or "ninguno"
            print(f"No existe el rol {a.rol!r}. Roles: {existentes}. No se escribió nada.",
                  file=sys.stderr)
            return 1

        ids = [r.id for r in u.roles]
        if a.quitar:
            if rol.id not in ids:
                print(f"{a.email}: no tenía el rol {rol.nombre}")
                return 0
            ids.remove(rol.id)
            accion = "quitado"
        else:
            if rol.id in ids:
                print(f"{a.email}: ya tenía el rol {rol.nombre}")
                return 0
            ids.append(rol.id)
            accion = "asignado"

        motivo = reemplazar_roles(db, u, ids)
        if motivo:
            db.rollback()
            print(f"{motivo} No se escribió nada.", file=sys.stderr)
            return 1
        db.commit()
        roles = ", ".join(r.nombre for r in u.roles) or "ninguno"
        print(f"{a.email}: rol {rol.nombre} {accion} (roles: {roles})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
