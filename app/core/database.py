from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


# ─── BD Sueldos (solo lectura) ───────────────────────────────────────────────

engine_sueldos = create_engine(
    settings.url_sueldos,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionSueldos = sessionmaker(bind=engine_sueldos, autocommit=False, autoflush=False)


def get_db_sueldos():
    db = SessionSueldos()
    try:
        yield db
    finally:
        db.close()


# ─── BD Externa (solo lectura) ───────────────────────────────────────────────

# Tope de lectura SOLO en la externa (servidor de ADCP, fuera de nuestro
# control). Incidente 2026-09-18: ese servidor quedó bloqueado 12 min y la
# consulta principal (2 s normalmente) colgó hasta 719 s; el front cortó a los
# 300 s sin mensaje útil. Con read_timeout, pymysql corta la espera y levanta
# OperationalError 2013, que el módulo traduce a un error claro para el usuario.
# La propia no lleva tope: escribe, y no queremos cortarla a mitad de un commit.
CONNECT_ARGS_EXTERNA = {"read_timeout": 60, "connect_timeout": 10}


class ExternaNoDisponible(Exception):
    """La base externa (ADCP) no respondió: venció el read_timeout o el servidor
    no está. Vive en el núcleo porque el engine que la origina es del núcleo y
    main.py la convierte en 503 para cualquier módulo (ADR-0013: el núcleo no
    importa módulos). El mensaje está pensado para mostrárselo al usuario tal cual."""

engine_externa = create_engine(
    settings.url_externa,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args=CONNECT_ARGS_EXTERNA,
)

SessionExterna = sessionmaker(bind=engine_externa, autocommit=False, autoflush=False)


# ─── BD Propia (lectura/escritura) ───────────────────────────────────────────

engine_propia = create_engine(
    settings.url_propia,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionPropia = sessionmaker(bind=engine_propia, autocommit=False, autoflush=False)


# ─── Base ORM ─────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Dependencias FastAPI ─────────────────────────────────────────────────────

def get_db_externa():
    db = SessionExterna()
    try:
        yield db
    finally:
        db.close()


def get_db_propia():
    db = SessionPropia()
    try:
        yield db
    finally:
        db.close()


# ─── Verificación de conectividad ────────────────────────────────────────────

def verificar_conexiones() -> dict:
    resultado = {"sueldos": False, "externa": False, "propia": False, "errores": []}
    try:
        with engine_sueldos.connect() as conn:
            conn.execute(text("SELECT 1"))
        resultado["sueldos"] = True
    except Exception as e:
        resultado["errores"].append(f"BD sueldos: {str(e)}")
    try:
        with engine_externa.connect() as conn:
            conn.execute(text("SELECT 1"))
        resultado["externa"] = True
    except Exception as e:
        resultado["errores"].append(f"BD externa: {str(e)}")
    try:
        with engine_propia.connect() as conn:
            conn.execute(text("SELECT 1"))
        resultado["propia"] = True
    except Exception as e:
        resultado["errores"].append(f"BD propia: {str(e)}")
    return resultado
