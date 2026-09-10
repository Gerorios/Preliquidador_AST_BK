"""Administración del Sistema: usuarios, roles globales y roles por módulo.

Es del NÚCLEO, no de un módulo: solo el rol global 'admin' entra (ver
CONTEXT.md, "Admin"). El alta sale del padrón de empleados (`nuempleados`,
solo lectura) y la identidad de la persona es su CUIL (ver
app/core/identidad.py).

No conoce módulos por nombre: valida las claves contra `permisos.MODULOS`, que
un test de arquitectura mantiene igual al registro de módulos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import invalidar_cache_usuarios
from app.core.database import get_db_propia, get_db_sueldos
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import RolUsuario, Usuario
from app.core.permisos import MODULOS, ROLES_MODULO, requiere_admin
from app.core.sueldos_service import SueldosService
from app.core import usuarios_service

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
    }


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
