"""Alta y mantenimiento de usuarios del Sistema (PR 5 de la etapa 0).

Lo usa la API de Administración (`app/core/administracion.py`).

Las validaciones devuelven el motivo del rechazo como texto (o None), no
excepciones HTTP: el service no conoce el transporte.
"""
from sqlalchemy.orm import Session

from app.core.auth import pwd_context
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import Usuario
from app.core.roles_service import buscar_roles


def crear_usuarios_lote(db: Session, personas: list[dict], rol_global: str,
                        roles: list[int]) -> dict:
    """Crea un usuario por persona del padrón, todas con los mismos `roles`
    (ids de roles armables, ADR-0020). No aborta el lote por una persona que
    falle: informa los omitidos con su motivo.

    Si algún id de rol no existe no crea a nadie y levanta ValueError con el
    motivo de `roles_service.buscar_roles` (el mismo texto que
    PUT /usuarios/{id}/roles), como `resetear_password` con un dato inválido.

    personas: [{'cuil': str, 'apellido_nombre': str}]
    """
    roles_del_lote, motivo = buscar_roles(db, roles)
    if motivo:
        raise ValueError(motivo)
    creados, omitidos = [], []

    for persona in personas:
        cuil_crudo = persona.get("cuil")
        cuil = normalizar_cuil(cuil_crudo)
        if not cuil:
            omitidos.append({"cuil": cuil_crudo, "motivo": "CUIL inválido"})
            continue

        email = email_de_cuil(cuil)
        if db.query(Usuario).filter(Usuario.email == email).first():
            omitidos.append({"cuil": cuil, "motivo": "ya tiene usuario"})
            continue

        usuario = Usuario(
            nombre=(persona.get("apellido_nombre") or "").strip() or cuil,
            email=email,
            password=pwd_context.hash(cuil),   # contraseña inicial = el CUIL
            rol=rol_global,
            activo=True,
            roles=list(roles_del_lote),
        )
        db.add(usuario)
        db.flush()                             # el id para la respuesta
        creados.append({"id": usuario.id, "cuil": cuil,
                        "nombre": usuario.nombre, "email": email})

    db.commit()
    return {"creados": creados, "omitidos": omitidos}


def resetear_password(db: Session, usuario: Usuario, password: str | None = None) -> str:
    """Deja la contraseña en el CUIL de la persona y la devuelve para mostrarla.

    Un usuario con mail real (los anteriores al PR 5) no tiene CUIL de dónde
    derivarla: en ese caso `password` es obligatoria.
    """
    nueva = password or cuil_de_email(usuario.email)
    if not nueva:
        raise ValueError(
            "Este usuario no tiene CUIL (entra con mail real): indicá la contraseña nueva"
        )
    usuario.password = pwd_context.hash(nueva)
    db.commit()
    return nueva


def validar_cambio(db: Session, actor: Usuario, objetivo: Usuario, *,
                   activo: bool | None, rol: str | None) -> str | None:
    """Las tres protecciones que impiden quedarse afuera del sistema.
    Devuelve el motivo del rechazo, o None si el cambio es válido."""
    se_desactiva = activo is False
    pierde_admin = rol is not None and rol != "admin" and objetivo.rol == "admin"

    if actor.id == objetivo.id and se_desactiva:
        return "No podés desactivar tu propio usuario"
    if actor.id == objetivo.id and pierde_admin:
        return "No podés quitarte a vos mismo el rol de administrador"

    if objetivo.rol == "admin" and objetivo.activo and (se_desactiva or pierde_admin):
        admins_activos = db.query(Usuario).filter(
            Usuario.rol == "admin", Usuario.activo == True  # noqa: E712
        ).count()
        if admins_activos <= 1:
            return "El sistema tiene que tener al menos un administrador activo"

    return None
