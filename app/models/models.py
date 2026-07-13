from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Date, Numeric, Text, Enum, ForeignKey, UniqueConstraint, Index
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

class UnidadBaseConcepto(str, enum.Enum):
    HSJORNAL    = "hsjornal"
    HSMAQUINA   = "hsmaquina"
    TANCADAS    = "tancadas"
    UNIDADES    = "unidades"
    JORNAL_TOPE1 = "jornal_tope1"
    FIJO        = "fijo"


# ─── Usuarios ─────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String(100), nullable=False)
    email      = Column(String(100), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    rol        = Column(String(20), default='jefe')
    contratos  = Column(String(50))
    activo     = Column(Boolean, default=True)
    creado_en  = Column(DateTime, default=datetime.utcnow)


# ─── Maestro unificado de Conceptos de Liquidación ───────────────────────────
#
# Reemplaza precio_maestro + precio_comun + concepto_liquidacion anterior.
#
# TIPO COMÚN:     cliente_nombre IS NULL  → aplica a todas las líneas con esa tarea
# TIPO ESPECÍFICO: cliente_nombre NOT NULL → aplica solo a cliente+finca exactos
#
# Matching: tarea_nombre + cliente_nombre + finca_nombre + quincena
# El campo grupo_pago fue eliminado — la unidad_base define el cálculo de cada regla.
# Ambos tipos siempre SUMAN (nunca se reemplazan).

class ConceptoLiquidacion(Base):
    __tablename__ = "concepto_liquidacion"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    quincena       = Column(Date, nullable=False)
    tarea_nombre   = Column(String(200), nullable=False)
    cliente_nombre = Column(String(150), nullable=True)   # NULL = común
    finca_nombre   = Column(String(150), nullable=True)   # NULL solo si cliente también es NULL
    codigo         = Column(Integer, nullable=True)
    unidad_base    = Column(
        Enum(UnidadBaseConcepto, values_callable=lambda e: [x.value for x in e]),
        default=UnidadBaseConcepto.FIJO,
        nullable=False,
    )
    precio         = Column(Numeric(12, 4))
    tipo           = Column(Enum(TipoConcepto), default=TipoConcepto.OTRO, nullable=False)
    heredado       = Column(Boolean, default=False, nullable=False)  # ADR-0004: precio copiado de otra quincena, sin confirmar
    # ADR-0008: categoría (1-7) de mantenimiento mecánico. NULL = concepto
    # común, se comporta igual que siempre. Con valor, el concepto solo
    # aplica a líneas de personas cuya categoría (tabla categoria_operario,
    # por quincena) coincida exactamente.
    categoria      = Column(Integer, nullable=True)
    # WS11: tilde opcional, solo tiene sentido en un concepto ESPECÍFICO
    # (cliente_nombre NOT NULL). Si una línea matchea un específico con
    # reemplaza_comun=True, se descartan los comunes de esa tarea para esa
    # línea (paga solo el/los específico/s). Default False: comportamiento
    # actual intacto (comunes y específicos suman).
    reemplaza_comun = Column(Boolean, default=False, nullable=False)
    creado_en      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "quincena", "tarea_nombre", "cliente_nombre", "finca_nombre", "codigo", "categoria",
            name="uq_concepto_unif",
        ),
    )


# ─── Preliquidación ───────────────────────────────────────────────────────────

class Preliquidacion(Base):
    __tablename__ = "preliquidacion"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    quincena   = Column(Date, nullable=False, unique=True)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    creado_en  = Column(DateTime, default=datetime.utcnow)
    # Valor hora de jornal de pulverización de esta quincena, que el liquidador
    # carga a mano (ADR-0007). Sirve para valorizar "a jornal" el trabajo de
    # pulverización y compararlo contra el pago "a tancada" en el control
    # Tancadas vs Jornal. Nullable: las quincenas viejas y las recién creadas
    # arrancan sin cargarlo, y en ese caso la comparación se muestra sin dato.
    valor_hora_pulv = Column(Numeric(12, 2), nullable=True)

    creador = relationship("Usuario")
    lineas  = relationship(
        "PreliquidacionLinea",
        back_populates="preliquidacion",
        cascade="all, delete-orphan",
    )


class PreliquidacionLinea(Base):
    __tablename__ = "preliquidacion_linea"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    preliquidacion_id  = Column(Integer, ForeignKey("preliquidacion.id"), nullable=False)

    # ── Datos de campo ──
    planilla           = Column(String(100))
    fecha_tarea        = Column(Date)
    nombre_cliente     = Column(String(150))
    nombre_finca       = Column(String(150))
    nombre_tarea       = Column(String(200))
    nombre_tractor     = Column(String(150))
    legajo_campo       = Column(String(20))
    nombre_empleado    = Column(String(150))
    cuit               = Column(String(20))
    nombre_supervisor  = Column(String(150))
    nombre_capataz     = Column(String(150))
    implemento         = Column(String(150))
    unidades           = Column(Numeric(10, 2))
    tancadas           = Column(Numeric(10, 2))
    hsjornal           = Column(Numeric(6, 2))
    hsmaquina          = Column(Numeric(6, 2))
    cantidad           = Column(Numeric(10, 2))

    # ── Resolución del liquidador ──
    empresa_asignada   = Column(String(50))
    legajo_asignado    = Column(String(20))
    grupo_pago_aplicado = Column(String(50))
    codigo_liquidacion = Column(Integer)
    precio_a           = Column(Numeric(12, 4))
    importe_base       = Column(Numeric(14, 2))
    importe_total      = Column(Numeric(14, 2))
    observacion        = Column(Text)

    # ── Flags de validación ──
    es_duplicado       = Column(Boolean, default=False)
    alerta_legajo      = Column(Boolean, default=False)
    alerta_empresa     = Column(Boolean, default=False)
    linea_incompleta   = Column(Boolean, default=True)

    preliquidacion = relationship("Preliquidacion", back_populates="lineas")
    conceptos      = relationship(
        "ConceptoAdicional",
        back_populates="linea",
        cascade="all, delete-orphan",
    )
    ajustes = relationship(
        "AjusteManual",
        back_populates="linea",
        cascade="all, delete-orphan",
    )

    # WS9 (latencia, DIFERIBLE — ver migrations/ws9_indices_latencia.sql):
    # índices de solo velocidad, no cambian comportamiento observable.
    __table_args__ = (
        Index(
            "ix_linea_orden",
            "preliquidacion_id", "empresa_asignada", "nombre_empleado", "fecha_tarea",
        ),
        Index("ix_linea_cuit", "preliquidacion_id", "cuit"),
        Index("ix_linea_tarea", "preliquidacion_id", "nombre_tarea"),
    )


class ConceptoAdicional(Base):
    __tablename__ = "concepto_adicional"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    linea_id        = Column(Integer, ForeignKey("preliquidacion_linea.id"), nullable=False)
    descripcion     = Column(String(150), nullable=False)
    codigo_concepto = Column(Integer)
    tipo            = Column(Enum(TipoConcepto), default=TipoConcepto.OTRO)
    unidad_base     = Column(String(30))
    # Snapshot del cálculo en el momento exacto en que se generó: precio y
    # cantidad son los factores de importe = cantidad * precio. Se guardan
    # porque concepto_liquidacion.precio es mutable (se edita todo el tiempo,
    # ver ADR-0002) — sin este snapshot, "a qué precio se le pagó" quedaría
    # mintiendo apenas alguien edite el maestro más tarde.
    precio          = Column(Numeric(12, 4))
    cantidad        = Column(Numeric(10, 2))
    # Trazabilidad hacia la regla exacta del maestro que originó este
    # concepto (nullable: los conceptos manuales, sin código, no tienen
    # origen en el maestro). ON DELETE SET NULL: si se borra la regla del
    # maestro, el hecho histórico de plata pagada no se toca — solo se
    # pierde el link hacia una regla que ya no existe.
    concepto_liquidacion_id = Column(
        Integer, ForeignKey("concepto_liquidacion.id", ondelete="SET NULL"), nullable=True
    )
    importe         = Column(Numeric(12, 2), nullable=False)
    ingresado_por   = Column(Integer, ForeignKey("usuarios.id"))
    fecha           = Column(DateTime, default=datetime.utcnow)

    linea            = relationship("PreliquidacionLinea", back_populates="conceptos")
    usuario          = relationship("Usuario")
    concepto_origen  = relationship("ConceptoLiquidacion")

    # WS9 (latencia, DIFERIBLE — ver migrations/ws9_indices_latencia.sql).
    __table_args__ = (
        Index("ix_concepto_linea_ingresado", "linea_id", "ingresado_por"),
    )


class AjusteManual(Base):
    __tablename__ = "ajuste_manual"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    linea_id          = Column(Integer, ForeignKey("preliquidacion_linea.id"), nullable=False)
    campo_modificado  = Column(String(100))
    valor_anterior    = Column(Text)
    valor_nuevo       = Column(Text)
    motivo            = Column(Text)
    usuario_id        = Column(Integer, ForeignKey("usuarios.id"))
    fecha             = Column(DateTime, default=datetime.utcnow)

    linea   = relationship("PreliquidacionLinea", back_populates="ajustes")
    usuario = relationship("Usuario")


# ─── Categoría de operario para Mantenimiento mecánico (ADR-0008) ────────────
#
# La categoría (1-7) de cada operario se administra a mano por el liquidador,
# por quincena (una persona puede cambiar de categoría de una quincena a
# otra). Cruza con ConceptoLiquidacion.categoria por CUIL para decidir qué
# concepto de "MANTENIMIENTO MECANICO (TALLERES)" le corresponde a cada línea.

class CategoriaOperario(Base):
    __tablename__ = "categoria_operario"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    quincena  = Column(Date, nullable=False)
    cuil      = Column(String(20), nullable=False)
    categoria = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("quincena", "cuil", name="uq_categoria_operario"),
    )