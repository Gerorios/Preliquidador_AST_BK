from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Date, Numeric, Text, Enum, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class SituacionPago(str, enum.Enum):
    A = "A"
    B = "B"

class TipoConcepto(str, enum.Enum):
    REMUNERATIVO = "REMUNERATIVO"
    NO_REMUNERATIVO = "NO_REMUNERATIVO"
    JORNAL = "JORNAL"
    BONO_BOLSON = "BONO_BOLSON"
    OTRO = "OTRO"

class RolUsuario(str, enum.Enum):
    ADMIN = "admin"
    JEFE = "jefe"
    GERENTE = "gerente"

class PrecioUsado(str, enum.Enum):
    A = "A"
    B = "B"

class UnidadBaseConcepto(str, enum.Enum):
    HSJORNAL = "hsjornal"
    HSMAQUINA = "hsmaquina"
    TANCADAS = "tancadas"
    UNIDADES = "unidades"
    JORNAL_TOPE1 = "jornal_tope1"   # 1 si hsjornal > 0, sin importar cuántas horas
    FIJO = "fijo"                   # importe fijo, cantidad = 1


# ─── Usuarios (apunta a la tabla existente — NO la crea) ─────────────────────
# Esta clase solo le permite a SQLAlchemy hacer relaciones y queries.
# La tabla "usuarios" ya existe y no se toca.

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}  # no recrear si ya existe

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    rol = Column(String(20), default='jefe')  # admin, jefe, gerente
    contratos = Column(String(50))
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


# ─── Precios ──────────────────────────────────────────────────────────────────

class PrecioMaestro(Base):
    __tablename__ = "precio_maestro"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_nombre = Column(String(150), nullable=False)
    finca_nombre = Column(String(150), nullable=False)
    tarea_nombre = Column(String(200), nullable=False)
    grupo_pago_default = Column(String(50), nullable=False)
    grupo_pago_override = Column(String(50))
    quincena = Column(Date, nullable=False)
    precio_a = Column(Numeric(12, 4))
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "cliente_nombre", "finca_nombre", "tarea_nombre", "quincena",
            name="uq_precio_maestro"
        ),
    )


class PrecioComun(Base):
    __tablename__ = "precio_comun"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarea_nombre = Column(String(200), nullable=False)
    grupo_pago = Column(String(50), nullable=False)
    quincena = Column(Date, nullable=False)
    precio = Column(Numeric(12, 4), nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tarea_nombre", "grupo_pago", "quincena", name="uq_precio_comun"),
    )


# ─── Maestro de Conceptos de Liquidación ──────────────────────────────────────
# Tabla paralela al maestro de precios. Cada combinación
# (tarea + cliente + finca + grupo_pago) concatenada en `detalle`
# puede tener VARIAS reglas — una por cada código de liquidación
# que se le debe aplicar automáticamente (jornal remunerativo,
# no remunerativo, plus bins, etc.)

class ConceptoLiquidacion(Base):
    __tablename__ = "concepto_liquidacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle = Column(String(500), nullable=False)
    codigo = Column(Integer)  # puede ser NULL si todavía no se asignó
    unidad_base = Column(
        Enum(UnidadBaseConcepto, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=UnidadBaseConcepto.FIJO,
    )
    precio = Column(Numeric(12, 4))  # puede ser NULL → usa el precio_a de la línea
    tipo = Column(Enum(TipoConcepto), default=TipoConcepto.OTRO)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("detalle", "codigo", name="uq_detalle_codigo"),
    )


# ─── Preliquidación ───────────────────────────────────────────────────────────

class Preliquidacion(Base):
    __tablename__ = "preliquidacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quincena = Column(Date, nullable=False, unique=True)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    creador = relationship("Usuario")
    lineas = relationship(
        "PreliquidacionLinea",
        back_populates="preliquidacion",
        cascade="all, delete-orphan",
    )


class PreliquidacionLinea(Base):
    __tablename__ = "preliquidacion_linea"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preliquidacion_id = Column(Integer, ForeignKey("preliquidacion.id"), nullable=False)

    # ── Datos de campo (vienen de BD externa, no se modifican) ──
    planilla = Column(String(100))
    fecha_tarea = Column(Date)
    nombre_cliente = Column(String(150))
    nombre_finca = Column(String(150))
    nombre_tarea = Column(String(200))
    nombre_tractor = Column(String(150))
    legajo_campo = Column(String(20))
    nombre_empleado = Column(String(150))
    cuit = Column(String(20))
    nombre_supervisor = Column(String(150))
    nombre_capataz = Column(String(150))
    implemento = Column(String(150))
    unidades = Column(Numeric(10, 2))
    tancadas = Column(Numeric(10, 2))
    hsjornal = Column(Numeric(6, 2))
    hsmaquina = Column(Numeric(6, 2))
    cantidad = Column(Numeric(10, 2))

    # ── Resolución del liquidador ──
    empresa_asignada = Column(String(50))
    legajo_asignado = Column(String(20))
    grupo_pago_aplicado = Column(String(50))
    codigo_liquidacion = Column(Integer)  # código del concepto principal (maestro de conceptos)
    detalle_concepto = Column(String(500))  # detalle congelado al crear la línea (tarea+cliente+finca+grupo_pago de campo, NO se recalcula)
    precio_a = Column(Numeric(12, 4))
    precio_b = Column(Numeric(12, 4))
    precio_usado = Column(Enum(PrecioUsado), default=PrecioUsado.A)
    importe_base = Column(Numeric(14, 2))
    importe_total = Column(Numeric(14, 2))
    revisado = Column(Boolean, default=False)
    observacion = Column(Text)

    # ── Flags de validación ──
    es_duplicado = Column(Boolean, default=False)
    alerta_legajo = Column(Boolean, default=False)
    alerta_empresa = Column(Boolean, default=False)  # múltiples empresas posibles
    alerta_sin_precio = Column(Boolean, default=False)
    alerta_sin_codigo = Column(Boolean, default=False)  # combinación sin código en maestro conceptos

    preliquidacion = relationship("Preliquidacion", back_populates="lineas")
    conceptos = relationship(
        "ConceptoAdicional",
        back_populates="linea",
        cascade="all, delete-orphan",
    )
    ajustes = relationship(
        "AjusteManual",
        back_populates="linea",
        cascade="all, delete-orphan",
    )


class ConceptoAdicional(Base):
    __tablename__ = "concepto_adicional"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linea_id = Column(Integer, ForeignKey("preliquidacion_linea.id"), nullable=False)
    descripcion = Column(String(150), nullable=False)
    codigo_concepto = Column(Integer)  # código de liquidación del concepto
    tipo = Column(Enum(TipoConcepto), default=TipoConcepto.OTRO)
    unidad_base = Column(String(30))  # hsjornal, hsmaquina, tancadas, unidades, fijo
    importe = Column(Numeric(12, 2), nullable=False)
    ingresado_por = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime, default=datetime.utcnow)

    linea = relationship("PreliquidacionLinea", back_populates="conceptos")
    usuario = relationship("Usuario")


class AjusteManual(Base):
    __tablename__ = "ajuste_manual"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linea_id = Column(Integer, ForeignKey("preliquidacion_linea.id"), nullable=False)
    campo_modificado = Column(String(100))
    valor_anterior = Column(Text)
    valor_nuevo = Column(Text)
    motivo = Column(Text)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime, default=datetime.utcnow)

    linea = relationship("PreliquidacionLinea", back_populates="ajustes")
    usuario = relationship("Usuario")