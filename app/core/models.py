"""
Modelos del núcleo del sistema: lo que comparten todos los módulos.
Hoy solo el usuario. Los permisos por módulo (usuario_modulo) llegan en el PR 3.
"""
from datetime import datetime
import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.core.database import Base


class RolUsuario(str, enum.Enum):
    ADMIN = "admin"
    JEFE = "jefe"
    GERENTE = "gerente"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String(100), nullable=False)
    email      = Column(String(100), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    rol        = Column(String(20), default='jefe')
    activo     = Column(Boolean, default=True)
    creado_en  = Column(DateTime, default=datetime.utcnow)
