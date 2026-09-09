"""Alta y mantenimiento de usuarios del Sistema (PR 5 de la etapa 0).

Lo usan la API de Administración (`app/core/administracion.py`) y los scripts
de consola, que se mantienen como puerta de entrada de emergencia si el admin
quedara sin acceso a la pantalla.

Las validaciones devuelven el motivo del rechazo como texto (o None), no
excepciones HTTP: el service no conoce el transporte.
"""
from sqlalchemy.orm import Session

from app.core.auth import pwd_context
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import Usuario, UsuarioModulo


def reemplazar_modulos(db: Session, usuario: Usuario, pares: list[tuple[str, str]]) -> None:
    """Reemplaza los módulos del usuario por `pares` (modulo, rol).

    Borra los viejos y hace flush antes de asignar los nuevos: si se reasigna
    `usuario.modulos = [...]` directamente, SQLAlchemy intenta insertar las
    filas nuevas antes de borrar las huérfanas y choca contra la UNIQUE
    (usuario_id, modulo) con un IntegrityError.
    """
    for m in list(usuario.modulos):
        db.delete(m)
    db.flush()
    usuario.modulos = [UsuarioModulo(modulo=m, rol=r) for m, r in pares]


def crear_usuarios_lote(db: Session, personas: list[dict], rol_global: str,
                        modulos: dict[str, str]) -> dict:
    """Crea un usuario por persona del padrón. No aborta el lote por una que
    falle: informa los omitidos con su motivo.

    personas: [{'cuil': str, 'apellido_nombre': str}]
    """
    creados, omitidos = [], []
    pares = list(modulos.items())

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
        )
        db.add(usuario)
        db.flush()                             # necesita el id para usuario_modulo
        if pares:
            reemplazar_modulos(db, usuario, pares)
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
