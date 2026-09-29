"""
Modelos del núcleo del sistema: lo que comparten todos los módulos.
Hoy solo el usuario. Los permisos por módulo (usuario_modulo) llegan en el PR 3.
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
    """Rol GLOBAL del sistema. Los roles por módulo (operador/gerente) viven
    en usuario_modulo — ver app/core/permisos.py y ADR-0013."""
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

    # selectin: se carga en la misma consulta que el usuario, así el objeto
    # sigue usable después del expunge del cache de get_usuario_actual.
    modulos = relationship("UsuarioModulo", back_populates="usuario",
                           cascade="all, delete-orphan", lazy="selectin")


class UsuarioModulo(Base):
    """Rol de un usuario dentro de un módulo (ADR-0013). Una fila por usuario y
    módulo. Por convención no se le cargan filas al admin; el código no lo
    exige (`tiene_permiso` corta antes por `rol == 'admin'`)."""
    __tablename__ = "usuario_modulo"
    __table_args__ = (UniqueConstraint("usuario_id", "modulo", name="uq_usuario_modulo"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    modulo     = Column(String(30), nullable=False)   # 'preliquidacion' | 'terceros' | ...
    rol        = Column(String(20), nullable=False)   # 'operador' | 'gerente'
    creado_en  = Column(DateTime, default=ahora_utc, nullable=False)

    usuario = relationship("Usuario", back_populates="modulos")
