"""Modelos SQLAlchemy del módulo Liquidación Terceros.

Espejo de las migraciones de `migrations/terceros/`. **La fuente de verdad del
esquema son ellas, no esto** (regla 9 de GUIA-MODULOS): acá se declara lo mismo
para que el ORM pueda leer y escribir, y para que el chequeo de tablas faltantes
del arranque cubra al módulo.

Son dos familias:

  - **Los hechos** (001): la foto de lo que las cinco fuentes tenían cuando se
    generó la quincena. Todos tienen `quincena_efectiva` y `motivo_efectiva`,
    que es trabajo manual del liquidador: al regenerar, las filas que las tienen
    cargadas se protegen y se borran últimas.

  - **El tarifario** (002): los precios que se pactan con cada tercero, por
    quincena. Nada de acá sale de un sistema: todo se carga a mano.

Lo que todavía no está es el cálculo — aplicarle a cada hecho su tarifa es la
etapa 7, y las columnas del importe van con la migración de esa etapa.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
# Usuario vive en el núcleo. Se importa acá a propósito: `generada_por` tiene
# ForeignKey("usuarios.id"), que SQLAlchemy resuelve por nombre, así que importar
# este módulo tiene que registrar Usuario primero. No borrar.
from app.core.models import Usuario  # noqa: F401


class Liquidacion(Base):
    """Una quincena generada: cuándo se trajo y quién la trajo.

    Generar no congela nada — se puede volver a actualizar mientras el recibo no
    se haya emitido. Lo que congela es la Emisión, que es por Tercero y llega en
    la etapa 11.
    """
    __tablename__ = "terceros_liquidacion"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    quincena       = Column(Date, nullable=False, unique=True)
    generada_en    = Column(DateTime, nullable=False, default=datetime.now)
    generada_por   = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    actualizada_en = Column(DateTime, nullable=True)

    viajes       = relationship("Viaje", back_populates="liquidacion", cascade="all, delete-orphan")
    horas_servicio = relationship("HoraServicio", back_populates="liquidacion", cascade="all, delete-orphan")
    cargas       = relationship("CargaCombustible", back_populates="liquidacion", cascade="all, delete-orphan")
    repuestos    = relationship("Repuesto", back_populates="liquidacion", cascade="all, delete-orphan")
    reparaciones = relationship("HoraReparacion", back_populates="liquidacion", cascade="all, delete-orphan")


class Viaje(Base):
    """Un traslado de personal a una finca. Se le paga al dueño del colectivo."""
    __tablename__ = "terceros_viaje"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id = Column(Integer, ForeignKey("terceros_liquidacion.id"), nullable=False, index=True)
    # En el sistema de campo el `nombre` del colectivo es el de su dueño; se
    # guardan los dos para no perder cómo vino.
    tercero           = Column(String(150), nullable=True, index=True)
    colectivo_nombre  = Column(String(150), nullable=True)
    colectivo_patente = Column(String(30), nullable=True)
    fecha_uso         = Column(Date, nullable=True)
    fecha_carga       = Column(Date, nullable=True)
    cliente           = Column(String(150), nullable=True)
    finca             = Column(String(150), nullable=True)
    tarea             = Column(String(200), nullable=True)
    supervisor        = Column(String(150), nullable=True)
    capataz           = Column(String(150), nullable=True)
    chofer            = Column(String(150), nullable=True)
    cantidad_viajes   = Column(Numeric(12, 2), nullable=True)   # 0,5 es normal
    cant_personas     = Column(Integer, nullable=True)
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="viajes")


class HoraServicio(Base):
    """La maquinaria del Tercero trabajando en una finca. Se le paga."""
    __tablename__ = "terceros_hora_servicio"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id = Column(Integer, ForeignKey("terceros_liquidacion.id"), nullable=False, index=True)
    # NULL cuando la descripción de la máquina traía una patente en vez de un
    # nombre: el hueco se muestra, no se rellena.
    tercero        = Column(String(150), nullable=True, index=True)
    fecha          = Column(Date, nullable=True)
    planilla       = Column(String(20), nullable=True)   # COSECHA | MAQUINARIA | PULVERIZADA
    cliente        = Column(String(150), nullable=True)
    finca          = Column(String(150), nullable=True)
    tarea          = Column(String(200), nullable=True)
    maquinaria     = Column(String(200), nullable=True)
    supervisor     = Column(String(150), nullable=True)
    # Las dos medidas sobre las que se puede pactar. Cuál se paga lo decide la
    # Unidad base de la tarifa, no el dato.
    horas_maquina  = Column(Numeric(10, 2), nullable=True)
    unidades       = Column(Numeric(12, 2), nullable=True)   # sólo planilla MAQUINARIA
    unidad         = Column(String(30), nullable=True)       # BINS, TANCADAS… informativa
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="horas_servicio")


class CargaCombustible(Base):
    """Litros que cargó un colectivo. Se le descuentan al dueño."""
    __tablename__ = "terceros_carga_combustible"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id = Column(Integer, ForeignKey("terceros_liquidacion.id"), nullable=False, index=True)
    tercero           = Column(String(150), nullable=True, index=True)
    colectivo_nombre  = Column(String(150), nullable=True)
    colectivo_patente = Column(String(30), nullable=True)
    fecha_uso         = Column(Date, nullable=True)
    fecha_carga       = Column(Date, nullable=True)
    litros            = Column(Numeric(12, 2), nullable=True)
    # La clave con la que después se concilia contra lo que factura la estación.
    vale              = Column(String(30), nullable=True, index=True)
    origen            = Column(String(150), nullable=True)
    usuario_carga     = Column(String(150), nullable=True)
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="cargas")


class Repuesto(Base):
    """Lo que salió del taller hacia una máquina del Tercero. Se le descuenta."""
    __tablename__ = "terceros_repuesto"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id = Column(Integer, ForeignKey("terceros_liquidacion.id"), nullable=False, index=True)
    tercero        = Column(String(150), nullable=True, index=True)
    id_maquina     = Column(Integer, nullable=True)      # el del sistema de compras
    maquina        = Column(String(200), nullable=True)
    # La del encabezado del movimiento: es la que hoy decide la quincena.
    fecha          = Column(Date, nullable=True)
    # La de la descarga a la maquinaria: es la correcta. Se guardan las dos para
    # medir el desvío antes de cambiar el criterio.
    fecha_descarga = Column(Date, nullable=True)
    tipo_insumo    = Column(String(60), nullable=True)
    rubro          = Column(String(100), nullable=True)
    repuesto       = Column(String(200), nullable=True)
    cantidad       = Column(Numeric(12, 2), nullable=True)
    # Vienen calculados del sistema de compras; el módulo no los recalcula.
    precio_unitario = Column(Numeric(14, 4), nullable=True)
    monto_total     = Column(Numeric(14, 4), nullable=True)
    reparacion      = Column(String(1), nullable=True)
    proveedor       = Column(String(150), nullable=True)
    # Hay salidas que no se le cobran al tercero.
    no_cobrar        = Column(Boolean, nullable=False, default=False)
    motivo_no_cobrar = Column(String(255), nullable=True)
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="repuestos")


class HoraReparacion(Base):
    """Horas del taller sobre una máquina del Tercero. Se le descuentan."""
    __tablename__ = "terceros_hora_reparacion"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id = Column(Integer, ForeignKey("terceros_liquidacion.id"), nullable=False, index=True)
    tercero        = Column(String(150), nullable=True, index=True)
    id_maquina     = Column(Integer, nullable=True)      # el de la app del taller
    maquina        = Column(String(200), nullable=True)
    tipo_maquina   = Column(String(60), nullable=True)
    fecha          = Column(Date, nullable=True)
    rubro          = Column(String(100), nullable=True)
    sub_rubro      = Column(String(200), nullable=True)
    finca          = Column(String(150), nullable=True)
    lugar          = Column(String(150), nullable=True)
    # Aprobado o Pendiente. Las rechazadas ni llegan: no se cobran nunca.
    estado            = Column(String(30), nullable=True)
    horas             = Column(Numeric(10, 2), nullable=True)
    horas_preparacion = Column(Numeric(10, 2), nullable=True)
    horas_traslado    = Column(Numeric(10, 2), nullable=True)
    horas_total       = Column(Numeric(10, 2), nullable=True)
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)

    liquidacion = relationship("Liquidacion", back_populates="reparaciones")

# ─── El Tarifario (etapa 6) ─────────────────────────────────────────────────
#
# Cinco tablas, una por cada cosa que se paga o se descuenta, todas por
# quincena. Las dimensiones que no participan se guardan como '' y no como
# NULL: en MySQL un UNIQUE deja pasar varias filas con NULL, y dos reglas
# idénticas son justo el empate que el módulo no sabe resolver. Con '' el
# índice único lo impide (ver migrations/terceros/002_tarifario.sql).
#
# La regla más específica es la que tiene más dimensiones distintas de ''.

SIN_DIMENSION = ""

# Sobre qué medida se calcula una Tarifa de servicio. Los mismos valores que la
# Unidad base de Preliquidación, a propósito: es el mismo concepto.
UNIDAD_HORA_MAQUINA = "hsmaquina"
UNIDAD_CANTIDAD = "unidades"
UNIDADES_BASE = (UNIDAD_HORA_MAQUINA, UNIDAD_CANTIDAD)

TIPO_VIAJE_CORTO = "CORTO"
TIPO_VIAJE_LARGO = "LARGO"
TIPOS_VIAJE = (TIPO_VIAJE_CORTO, TIPO_VIAJE_LARGO)


class TarifaViaje(Base):
    """Cuánto se le paga un viaje a un tercero, y si es corto o largo.

    El tipo no es clave de la regla sino su resultado: la misma regla que fija
    el precio fija el tipo. No se deduce del destino — un mismo cliente y finca
    tiene viajes de los dos tipos.
    """
    __tablename__ = "terceros_tarifa_viaje"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    quincena   = Column(Date, nullable=False, index=True)
    tercero    = Column(String(150), nullable=False, default=SIN_DIMENSION)
    cliente    = Column(String(150), nullable=False, default=SIN_DIMENSION)
    finca      = Column(String(150), nullable=False, default=SIN_DIMENSION)
    capataz    = Column(String(150), nullable=False, default=SIN_DIMENSION)
    tipo_viaje = Column(String(10), nullable=True)
    precio     = Column(Numeric(14, 2), nullable=False)
    # Vino copiada de otra quincena y nadie la confirmó. Paga igual.
    heredada   = Column(Boolean, nullable=False, default=False)
    creado_en  = Column(DateTime, nullable=False, default=datetime.now)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero", "cliente", "finca", "capataz")

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", "cliente", "finca", "capataz",
                         name="uq_terceros_tarifa_viaje"),
    )


class TarifaServicio(Base):
    """Cuánto se le paga al tercero por el trabajo de su maquinaria."""
    __tablename__ = "terceros_tarifa_servicio"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    quincena    = Column(Date, nullable=False, index=True)
    tercero     = Column(String(150), nullable=False, default=SIN_DIMENSION)
    cliente     = Column(String(150), nullable=False, default=SIN_DIMENSION)
    finca       = Column(String(150), nullable=False, default=SIN_DIMENSION)
    tarea       = Column(String(200), nullable=False, default=SIN_DIMENSION)
    # 'hsmaquina' o 'unidades': qué se multiplica por el precio.
    unidad_base = Column(String(20), nullable=False)
    precio      = Column(Numeric(14, 2), nullable=False)
    heredada    = Column(Boolean, nullable=False, default=False)
    creado_en   = Column(DateTime, nullable=False, default=datetime.now)
    creado_por  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero", "cliente", "finca", "tarea")

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", "cliente", "finca", "tarea",
                         name="uq_terceros_tarifa_servicio"),
    )


class PrecioCombustible(Base):
    """Precio por litro que se le descuenta a un tercero."""
    __tablename__ = "terceros_precio_combustible"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    quincena   = Column(Date, nullable=False, index=True)
    tercero    = Column(String(150), nullable=False)
    precio     = Column(Numeric(14, 4), nullable=False)
    heredada   = Column(Boolean, nullable=False, default=False)
    creado_en  = Column(DateTime, nullable=False, default=datetime.now)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero",)

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", name="uq_terceros_precio_combustible"),
    )


class PrecioReparacion(Base):
    """Precio de la hora de taller, por tercero."""
    __tablename__ = "terceros_precio_reparacion"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    quincena   = Column(Date, nullable=False, index=True)
    tercero    = Column(String(150), nullable=False)
    precio     = Column(Numeric(14, 2), nullable=False)
    heredada   = Column(Boolean, nullable=False, default=False)
    creado_en  = Column(DateTime, nullable=False, default=datetime.now)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero",)

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", name="uq_terceros_precio_reparacion"),
    )


class PrecioSeguro(Base):
    """La cuota de la póliza de una máquina. La carga a mano quien tiene los
    seguros a cargo: no llega por archivo ni sale de ningún sistema."""
    __tablename__ = "terceros_precio_seguro"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    quincena   = Column(Date, nullable=False, index=True)
    tercero    = Column(String(150), nullable=False)
    maquinaria = Column(String(200), nullable=False)
    importe    = Column(Numeric(14, 2), nullable=False)
    heredada   = Column(Boolean, nullable=False, default=False)
    creado_en  = Column(DateTime, nullable=False, default=datetime.now)
    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero", "maquinaria")

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", "maquinaria", name="uq_terceros_precio_seguro"),
    )
