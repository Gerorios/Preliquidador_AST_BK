"""
Modelos del núcleo del sistema: lo que comparten todos los módulos.
El usuario y sus roles con permisos por pantalla (ADR-0020).
"""
from datetime import UTC, datetime
import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


def ahora_utc() -> datetime:
    """Default de las columnas de fecha de alta: ahora en UTC, **naive**.

    Reemplaza a `datetime.utcnow()` (deprecada desde Python 3.12) con el mismo
    valor. Naive a propósito: las columnas son `DateTime` sin zona (MySQL
    DATETIME y SQLite no la guardan) y SQLAlchemy devuelve naive al leer; un
    default aware haría convivir objetos aware (recién creados) con naive
    (cargados) y compararlos u ordenarlos levantaría TypeError. Vive en el
    núcleo porque la usan los modelos del núcleo y los de los módulos."""
    return datetime.now(UTC).replace(tzinfo=None)


class RolUsuario(str, enum.Enum):
    """Rol GLOBAL del sistema: 'admin' pasa todo. Lo que ve y edita cada
    'usuario' lo dan sus roles (`Usuario.roles`) — ver app/core/permisos.py y
    ADR-0020."""
    ADMIN = "admin"
    USUARIO = "usuario"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String(100), nullable=False)
    email      = Column(String(100), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    rol        = Column(String(20), default='usuario')
    activo     = Column(Boolean, default=True)
    creado_en  = Column(DateTime, default=ahora_utc)

    # Roles armables (ADR-0020). selectin: se cargan junto con el usuario, así
    # el objeto sigue usable después del expunge del cache de
    # get_usuario_actual. El expunge en la cascada NO es opcional: sin él, el
    # `db.expunge(usuario)` de get_usuario_actual deja los Rol en la sesión de
    # la request; si esa request hace commit quedan vencidos, al cerrarse quedan
    # desligados, y la request siguiente que lea sus permisos desde el cache
    # revienta con DetachedInstanceError. Sin delete: borrar a la persona no
    # borra el rol.
    roles = relationship("Rol", secondary="usuario_rol", lazy="selectin",
                         cascade="save-update, merge, expunge")


class Rol(Base):
    """Rol que arma el admin en Administración (ADR-0020): un nombre y sus
    permisos de ver o editar por pantalla. Los permisos de varios roles se
    suman en la persona; la marca global de admin (`Usuario.rol`) no pasa por
    acá."""
    __tablename__ = "rol"
    __table_args__ = (UniqueConstraint("nombre", name="uq_rol_nombre"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String(60), nullable=False)
    creado_en  = Column(DateTime, default=ahora_utc, nullable=False)

    # cascade "all" incluye expunge: los permisos se desligan junto con el rol
    # cuando get_usuario_actual desliga a la persona.
    permisos = relationship("RolPermiso", cascade="all, delete-orphan", lazy="selectin")


class RolPermiso(Base):
    """Permiso de un rol sobre una pantalla de un módulo. "Sin acceso" es que no
    haya fila; las claves de módulo y pantalla son las del catálogo
    (`ModuloInfo.pantallas`)."""
    __tablename__ = "rol_permiso"
    __table_args__ = (UniqueConstraint("rol_id", "modulo", "pantalla", name="uq_rol_permiso"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    rol_id     = Column(Integer, ForeignKey("rol.id", ondelete="CASCADE"), nullable=False)
    modulo     = Column(String(30), nullable=False)   # 'preliquidacion' | 'terceros' | ...
    pantalla   = Column(String(40), nullable=False)   # clave de la pantalla en el catálogo
    nivel      = Column(String(10), nullable=False)   # 'ver' | 'editar'


class UsuarioRol(Base):
    """Qué roles tiene cada persona. Sin relaciones propias a propósito: la
    tabla la maneja `Usuario.roles` como `secondary`, y dos caminos de escritura
    sobre las mismas filas se pisarían."""
    __tablename__ = "usuario_rol"
    __table_args__ = (UniqueConstraint("usuario_id", "rol_id", name="uq_usuario_rol"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    rol_id     = Column(Integer, ForeignKey("rol.id", ondelete="RESTRICT"), nullable=False)
    creado_en  = Column(DateTime, default=ahora_utc, nullable=False)
