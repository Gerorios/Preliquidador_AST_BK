"""Administración del Sistema: usuarios, roles globales, roles por módulo y
roles armables (ADR-0020).

Es del NÚCLEO, no de un módulo: solo el rol global 'admin' entra (ver
CONTEXT.md, "Admin"). El alta sale del padrón de empleados (`nuempleados`,
solo lectura) y la identidad de la persona es su CUIL (ver
app/core/identidad.py).

No conoce módulos por nombre: valida las claves contra `permisos.MODULOS`, que
un test de arquitectura mantiene igual al registro de módulos. Los permisos de
los roles se validan contra el catálogo de módulos activos que llega por
`app.state` (`modulos.catalogo_activo`).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import invalidar_cache_usuarios
from app.core.database import get_db_propia, get_db_sueldos
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import Rol, RolUsuario, Usuario, UsuarioRol
from app.core.modulos import ModuloInfo, catalogo_activo
from app.core.permisos import MODULOS, ROLES_MODULO, requiere_admin
from app.core.sueldos_service import SueldosService
from app.core import roles_service, usuarios_service

# UNA instancia de la dependencia, reusada en el router y en los endpoints que
# necesitan el usuario que hace el cambio. Si se llamara `requiere_admin()` en
# cada lugar, FastAPI vería funciones distintas y la ejecutaría más de una vez
# por request (su cache de dependencias es por objeto).
DEP_ADMIN = requiere_admin()

router = APIRouter(prefix="/api/admin", tags=["Administración"],
                   dependencies=[Depends(DEP_ADMIN)])

ROLES_GLOBALES = tuple(r.value for r in RolUsuario)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AltaLote(BaseModel):
    cuils: list[str]
    rol_global: str = RolUsuario.USUARIO.value
    modulos: dict[str, str] = {}


class CambioUsuario(BaseModel):
    nombre: str | None = None
    rol: str | None = None
    activo: bool | None = None


class CambioModulos(BaseModel):
    modulos: dict[str, str]


class ResetPassword(BaseModel):
    password: str | None = None


class DatosRol(BaseModel):
    nombre: str = ""
    # {modulo: {pantalla: nivel}}; nivel "ver" o "editar" (None, "" o "sin" es
    # sin acceso, como en el editor del front).
    permisos: roles_service.Permisos = {}


class CambioRoles(BaseModel):
    roles: list[int]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _publico(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "cuil": cuil_de_email(usuario.email),
        "rol": usuario.rol,
        "activo": bool(usuario.activo),
        "modulos": {m.modulo: m.rol for m in usuario.modulos},
        "roles": [{"id": r.id, "nombre": r.nombre}
                  for r in sorted(usuario.roles, key=lambda r: (r.nombre, r.id))],
    }


def _rol_publico(rol: Rol, personas: list[Usuario]) -> dict:
    permisos: dict[str, dict[str, str]] = {}
    for p in rol.permisos:
        permisos.setdefault(p.modulo, {})[p.pantalla] = p.nivel
    return {
        "id": rol.id,
        "nombre": rol.nombre,
        "permisos": permisos,
        "personas": [{"id": u.id, "nombre": u.nombre, "activo": bool(u.activo)} for u in personas],
    }


def _buscar_rol(db: Session, rol_id: int) -> Rol:
    rol = db.query(Rol).filter(Rol.id == rol_id).first()
    if not rol:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El rol no existe")
    return rol


def _rechazar_rol(motivo: str):
    """El nombre repetido es un conflicto (409); el resto, una validación (400).
    Se reconoce como lo indica `roles_service`: con `es_nombre_repetido`, que
    cubre también el choque contra la UNIQUE en el commit (no se ve consultando)."""
    repetido = roles_service.es_nombre_repetido(motivo)
    codigo = status.HTTP_409_CONFLICT if repetido else status.HTTP_400_BAD_REQUEST
    raise HTTPException(codigo, motivo)


def _validar_modulos(modulos: dict[str, str]) -> None:
    for clave, rol in modulos.items():
        if clave not in MODULOS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Módulo inexistente: {clave}")
        if rol not in ROLES_MODULO:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Rol inválido para {clave}: {rol}")


def _validar_rol_global(rol: str) -> None:
    if rol not in ROLES_GLOBALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Rol global inválido: {rol}")


def _buscar(db: Session, usuario_id: int) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no existe")
    return usuario


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db_propia)):
    usuarios = db.query(Usuario).order_by(Usuario.nombre).all()
    return [_publico(u) for u in usuarios]


@router.get("/padron")
def buscar_en_padron(
    q: str = Query(..., min_length=3, description="Apellido, nombre o CUIL"),
    db: Session = Depends(get_db_propia),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Personas del padrón de empleados, marcando quién ya tiene usuario."""
    resultado = SueldosService(db_sueldos).buscar_personas(q)
    emails = {u.email for u in db.query(Usuario.email).all()}
    personas = [
        {**p, "ya_tiene_usuario": bool(p["cuil"]) and email_de_cuil(p["cuil"]) in emails}
        for p in resultado["personas"]
    ]
    return {"personas": personas, "total": resultado["total"]}


@router.post("/usuarios")
def crear_usuarios(
    datos: AltaLote,
    db: Session = Depends(get_db_propia),
    db_sueldos: Session = Depends(get_db_sueldos),
):
    """Alta de una o varias personas del padrón, todas con los mismos roles."""
    _validar_rol_global(datos.rol_global)
    _validar_modulos(datos.modulos)

    padron = SueldosService(db_sueldos)
    personas, omitidos = [], []
    for crudo in datos.cuils:
        cuil = normalizar_cuil(crudo)
        if not cuil:
            omitidos.append({"cuil": crudo, "motivo": "CUIL inválido"})
            continue
        encontrada = next(
            (p for p in padron.buscar_personas(cuil)["personas"] if p["cuil"] == cuil), None
        )
        if not encontrada:
            omitidos.append({"cuil": cuil, "motivo": "no está en el padrón"})
            continue
        personas.append({"cuil": cuil, "apellido_nombre": encontrada["apellido_nombre"]})

    resultado = usuarios_service.crear_usuarios_lote(
        db, personas, datos.rol_global, datos.modulos
    )
    resultado["omitidos"] = omitidos + resultado["omitidos"]
    invalidar_cache_usuarios()
    return resultado


@router.patch("/usuarios/{usuario_id}")
def actualizar_usuario(
    usuario_id: int,
    cambio: CambioUsuario,
    actor: Usuario = Depends(DEP_ADMIN),
    db: Session = Depends(get_db_propia),
):
    usuario = _buscar(db, usuario_id)
    if cambio.rol is not None:
        _validar_rol_global(cambio.rol)

    motivo = usuarios_service.validar_cambio(
        db, actor, usuario, activo=cambio.activo, rol=cambio.rol
    )
    if motivo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, motivo)

    if cambio.nombre is not None:
        usuario.nombre = cambio.nombre.strip()
    if cambio.rol is not None:
        usuario.rol = cambio.rol
    if cambio.activo is not None:
        usuario.activo = cambio.activo
    db.commit()
    invalidar_cache_usuarios()
    return _publico(usuario)


@router.put("/usuarios/{usuario_id}/modulos")
def actualizar_modulos(
    usuario_id: int,
    cambio: CambioModulos,
    db: Session = Depends(get_db_propia),
):
    _validar_modulos(cambio.modulos)
    usuario = _buscar(db, usuario_id)
    usuarios_service.reemplazar_modulos(db, usuario, list(cambio.modulos.items()))
    db.commit()
    invalidar_cache_usuarios()
    return _publico(usuario)


@router.post("/usuarios/{usuario_id}/password")
def resetear_password(
    usuario_id: int,
    datos: ResetPassword,
    db: Session = Depends(get_db_propia),
):
    """Deja la contraseña en el CUIL de la persona y la devuelve para pasársela."""
    usuario = _buscar(db, usuario_id)
    try:
        nueva = usuarios_service.resetear_password(db, usuario, datos.password)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    invalidar_cache_usuarios()
    return {"password": nueva}


# ─── Roles (ADR-0020) ─────────────────────────────────────────────────────────

@router.get("/roles")
def listar_roles(db: Session = Depends(get_db_propia)):
    """Los roles con sus permisos y quiénes los tienen (también las personas
    inactivas: si se reactivan, recuperan el acceso)."""
    roles = db.query(Rol).order_by(Rol.nombre, Rol.id).all()
    personas: dict[int, list[Usuario]] = {}
    filas = (
        db.query(UsuarioRol.rol_id, Usuario)
        .join(Usuario, Usuario.id == UsuarioRol.usuario_id)
        .order_by(Usuario.nombre, Usuario.id)
        .all()
    )
    for rol_id, usuario in filas:
        personas.setdefault(rol_id, []).append(usuario)
    return [_rol_publico(r, personas.get(r.id, [])) for r in roles]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def crear_rol(
    datos: DatosRol,
    catalogo: tuple[ModuloInfo, ...] = Depends(catalogo_activo),
    db: Session = Depends(get_db_propia),
):
    rol, motivo = roles_service.crear_rol(db, datos.nombre, datos.permisos, catalogo)
    if motivo:
        _rechazar_rol(motivo)
    invalidar_cache_usuarios()
    return _rol_publico(rol, [])


@router.put("/roles/{rol_id}")
def actualizar_rol(
    rol_id: int,
    datos: DatosRol,
    catalogo: tuple[ModuloInfo, ...] = Depends(catalogo_activo),
    db: Session = Depends(get_db_propia),
):
    """Reemplaza los permisos de los módulos activos (también los que no vienen)
    y conserva los de módulos inactivos, que el editor no muestra."""
    rol = _buscar_rol(db, rol_id)
    motivo = roles_service.actualizar_rol(db, rol, datos.nombre, datos.permisos, catalogo)
    if motivo:
        _rechazar_rol(motivo)
    invalidar_cache_usuarios()
    return _rol_publico(rol, roles_service.personas_con_rol(db, rol))


@router.delete("/roles/{rol_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_rol(rol_id: int, db: Session = Depends(get_db_propia)):
    """409 con el motivo si alguien tiene el rol (incluidas las inactivas)."""
    rol = _buscar_rol(db, rol_id)
    motivo = roles_service.borrar_rol(db, rol)
    if motivo:
        raise HTTPException(status.HTTP_409_CONFLICT, motivo)
    invalidar_cache_usuarios()


@router.put("/usuarios/{usuario_id}/roles")
def actualizar_roles_de_usuario(
    usuario_id: int,
    cambio: CambioRoles,
    db: Session = Depends(get_db_propia),
):
    """Reemplaza la lista completa de roles de la persona."""
    usuario = _buscar(db, usuario_id)
    motivo = roles_service.reemplazar_roles(db, usuario, cambio.roles)
    if motivo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, motivo)
    db.commit()
    invalidar_cache_usuarios()
    return _publico(usuario)
