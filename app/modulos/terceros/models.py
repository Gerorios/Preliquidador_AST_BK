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

  - **El cálculo** (004): a cada hecho se le pega la regla que lo alcanzó, el
    precio y el importe. Se guarda y no se calcula al vuelo porque el recibo se
    congela al emitirse, y porque la grilla filtra sobre estas columnas.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
# Usuario vive en el núcleo. Se importa acá a propósito: `generada_por` tiene
# ForeignKey("usuarios.id"), que SQLAlchemy resuelve por nombre, así que importar
# este módulo tiene que registrar Usuario primero. No borrar.
from app.core.models import Usuario  # noqa: F401

# ─── Los estados del cálculo (etapa 7) ──────────────────────────────────────
#
# Cuatro de los seis dicen por qué una línea NO tiene importe, y son razones
# distintas que resuelve gente distinta: un SIN_TERCERO lo arregla el sistema de
# campo, un SIN_TARIFA lo carga el liquidador, una NO_APROBADA la aprueba el
# taller. Por eso son estados con nombre y no un importe en NULL.
#
# Ninguno paga cero en silencio: los que no son CALCULADO se listan aparte.

CALCULADO = "CALCULADO"
SIN_TERCERO = "SIN_TERCERO"          # el hecho no tiene dueño resuelto
SIN_TARIFA = "SIN_TARIFA"            # ninguna regla lo alcanza
TARIFA_AMBIGUA = "TARIFA_AMBIGUA"    # dos reglas igual de específicas lo alcanzan
NO_COBRAR = "NO_COBRAR"              # se decidió no cobrarlo (repuestos)
NO_APROBADA = "NO_APROBADA"          # la hora de taller todavía no se aprobó
# Hay tarifa, pero la línea no trae la medida que esa tarifa cobra: una tarea
# pactada por cantidad sobre una planilla que sólo registró horas, por ejemplo.
# Es un error de configuración del tarifario, no un cero.
SIN_CANTIDAD = "SIN_CANTIDAD"

ESTADOS_CALCULO = (CALCULADO, SIN_TERCERO, SIN_TARIFA, TARIFA_AMBIGUA,
                   NO_COBRAR, NO_APROBADA, SIN_CANTIDAD)

# El signo no vive en el dato: `importe` es siempre positivo en las cinco
# tablas y el concepto decide de qué lado del recibo cae. Un viaje se paga y un
# repuesto se descuenta, y eso no cambia nunca por fila. Guardarlo con signo
# invitaría a que algún día entre un combustible en positivo y nadie lo note.
SE_PAGA = ("viajes", "servicio")
SE_DESCUENTA = ("combustible", "repuestos", "reparacion", "seguros")
SIGNO = {**{c: 1 for c in SE_PAGA}, **{c: -1 for c in SE_DESCUENTA}}


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
    # Distinta de `actualizada_en`: traer los hechos y ponerles precio son dos
    # cosas, y la segunda se rehace sola cada vez que cambia una tarifa.
    calculada_en   = Column(DateTime, nullable=True)

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
    # El tipo de viaje no viene del origen: lo resuelve la misma regla que fija
    # el precio, y se copia acá al calcular.
    tarifa_id       = Column(Integer, nullable=True)
    tipo_viaje      = Column(String(10), nullable=True)
    precio_aplicado = Column(Numeric(14, 4), nullable=True)
    importe         = Column(Numeric(14, 2), nullable=True)
    estado_calculo  = Column(String(20), nullable=False, default=SIN_TARIFA)

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
    tarifa_id       = Column(Integer, nullable=True)
    # Cuál de las dos medidas eligió la tarifa, y cuánto valía. Sin esto,
    # mirando la línea no se sabe sobre qué se multiplicó el precio.
    unidad_base     = Column(String(20), nullable=True)
    cantidad_base   = Column(Numeric(12, 2), nullable=True)
    precio_aplicado = Column(Numeric(14, 4), nullable=True)
    importe         = Column(Numeric(14, 2), nullable=True)
    estado_calculo  = Column(String(20), nullable=False, default=SIN_TARIFA)

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
    # Campo libre del sistema de campo. No identifica la carga —no va en la
    # clave— pero es lo que explica por qué un vale aparece dos veces.
    observacion       = Column(Text, nullable=True)
    quincena_efectiva = Column(Date, nullable=True)
    motivo_efectiva   = Column(String(255), nullable=True)
    tarifa_id       = Column(Integer, nullable=True)
    precio_aplicado = Column(Numeric(14, 4), nullable=True)
    importe         = Column(Numeric(14, 2), nullable=True)
    estado_calculo  = Column(String(20), nullable=False, default=SIN_TARIFA)

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
    # No lleva tarifa_id: el repuesto no se tarifa, ya viene con su monto.
    importe        = Column(Numeric(14, 2), nullable=True)
    estado_calculo = Column(String(20), nullable=False, default=CALCULADO)

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
    tarifa_id       = Column(Integer, nullable=True)
    precio_aplicado = Column(Numeric(14, 4), nullable=True)
    importe         = Column(Numeric(14, 2), nullable=True)
    estado_calculo  = Column(String(20), nullable=False, default=SIN_TARIFA)

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


# Las tres clases de póliza que llegan. La primera cubre una máquina o un
# vehículo; las otras dos cubren a una persona.
SEGURO_AUTOMOTOR = "AUTOMOTOR"
SEGURO_RELACION_DEPENDENCIA = "RELACION_DEPENDENCIA"
SEGURO_ACCIDENTES_PERSONALES = "ACCIDENTES_PERSONALES"
TIPOS_SEGURO = (SEGURO_AUTOMOTOR, SEGURO_RELACION_DEPENDENCIA,
                SEGURO_ACCIDENTES_PERSONALES)


class PrecioSeguro(Base):
    """La cuota de una póliza. La carga a mano quien tiene los seguros a cargo:
    no llega por archivo ni sale de ningún sistema.

    El sujeto no siempre es una máquina — el seguro del chofer cubre a una
    persona. Por eso `sujeto` y no `maquinaria`: meter el nombre de alguien en
    una columna que dice máquina deja la tabla ilegible para el que venga.
    """
    __tablename__ = "terceros_precio_seguro"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    quincena    = Column(Date, nullable=False, index=True)
    tercero     = Column(String(150), nullable=False)
    tipo_seguro = Column(String(30), nullable=False)
    # La máquina o la persona que cubre la póliza.
    sujeto      = Column(String(200), nullable=False)
    # Cómo se lo identifica: la patente si es un bien, el CUIL si es alguien.
    referencia  = Column(String(60), nullable=True)
    importe     = Column(Numeric(14, 2), nullable=False)
    heredada    = Column(Boolean, nullable=False, default=False)
    creado_en   = Column(DateTime, nullable=False, default=datetime.now)
    creado_por  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    DIMENSIONES = ("tercero", "tipo_seguro", "sujeto")

    __table_args__ = (
        UniqueConstraint("quincena", "tercero", "tipo_seguro", "sujeto",
                         name="uq_terceros_precio_seguro"),
    )
