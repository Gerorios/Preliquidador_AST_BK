import logging
import secrets
import sys
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# En Windows, sin PYTHONIOENCODING/PYTHONUTF8, stdout/stderr usan el codepage
# de la consola (p. ej. cp1252), que no soporta los caracteres Unicode que
# usan los prints de abajo. Sin esto, el lifespan revienta con
# UnicodeEncodeError al arrancar y el servidor nunca queda arriba.
# line_buffering: bajo systemd stdout es un pipe y Python lo guarda por
# bloques; sin esto el banner de arranque no llega al journal hasta que el
# proceso termina.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import importlib

from sqlalchemy import inspect

from app.core.config import guardia_base_propia, settings
from app.core.database import verificar_conexiones, engine_propia, Base
from app.core.esquema import comparar_esquema
from app.core import models as models_core   # noqa: F401 — registra las tablas del núcleo (usuarios)
from app.modulos import activos

# Registra los modelos de cada módulo activo (ADR-0013): el núcleo no importa
# módulos por nombre, recorre el registro. Los inactivos no aportan tablas al
# chequeo de tablas y columnas faltantes de más abajo.
for _modulo in activos():
    if _modulo.modelos:
        importlib.import_module(_modulo.modelos)

_log_esquema = logging.getLogger("app.esquema")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("─" * 50)
    print("  Sistema de gestión — La Asturiana SRL")
    print("─" * 50)

    # Única razón por la que se aborta el arranque: evita escribir sobre
    # producción desde una máquina de desarrollo. En el VPS no se dispara
    # porque su .env trae PERMITIR_BASE_PRODUCCION=1 (ponerlo ANTES de
    # deployar este código, o systemd entra en bucle de reinicios).
    motivo = guardia_base_propia(settings.db_propia_name, settings.permitir_base_produccion)
    if motivo:
        print(f"  ERROR: no arranco: {motivo}")
        print("─" * 50)
        raise SystemExit(f"No arranco: {motivo}")

    resultado = verificar_conexiones()
    print(f"  BD sueldos:  {'✓ OK' if resultado['sueldos'] else '✗ ERROR'}")
    print(f"  BD externa:  {'✓ OK' if resultado['externa'] else '✗ ERROR'}")
    print(f"  BD propia:   {'✓ OK' if resultado['propia'] else '✗ ERROR'} ({settings.db_propia_name.strip()})")

    if resultado["errores"]:
        for err in resultado["errores"]:
            print(f"  ERROR: {err}")

    # El esquema lo gobiernan las migraciones SQL (migrations/<modulo>/), que se
    # aplican a mano. No se crean tablas al arrancar: una tabla o columna que
    # el modelo pide y la base no tiene es un deploy incompleto (migración sin
    # aplicar). Acá no se aborta el arranque (systemd entraría en bucle de
    # reinicios): los nombres se imprimen bien visibles en el banner (quedan en
    # el journal) y /health sólo expone el booleano, sin nombres.
    app.state.esquema_incompleto = False
    if resultado["propia"]:
        # Un fallo del chequeo mismo (p. ej. la base se cae justo acá) tampoco
        # tumba el arranque: se loguea con traceback y la app sigue. El
        # booleano queda en False porque no hay evidencia de que falte nada;
        # el banner dice que no se pudo verificar.
        try:
            diferencias = comparar_esquema(Base.metadata, inspect(engine_propia))
        except Exception:
            _log_esquema.exception("No se pudo verificar el esquema de la base propia")
            print("  ERROR: no se pudo verificar el esquema de la base propia (ver log)")
        else:
            if diferencias.tablas_faltantes:
                print("  ERROR: faltan tablas en la base propia (migraciones sin aplicar): "
                      f"{', '.join(diferencias.tablas_faltantes)}")
            if diferencias.columnas_faltantes:
                print("  ERROR: faltan columnas en la base propia (migraciones sin aplicar): "
                      f"{', '.join(diferencias.columnas_faltantes)}")
            app.state.esquema_incompleto = bool(
                diferencias.tablas_faltantes or diferencias.columnas_faltantes
            )
            if not app.state.esquema_incompleto:
                print("  Tablas y columnas BD propia: verificadas")

    print("─" * 50)
    yield
    print("Servidor detenido.")


app = FastAPI(
    title="Sistema de gestión — La Asturiana SRL",
    version="1.0.0",
    lifespan=lifespan,
)

# La base externa (ADCP) no respondió (read_timeout vencido o servidor caído):
# 503 con el mensaje de la excepción, para cualquier módulo que la consulte.
# Sin esto, cada endpoint sin try/except devolvía 500 con el texto crudo de
# pymysql ("Lost connection to MySQL server during query").
from app.core.database import ExternaNoDisponible  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402


@app.exception_handler(ExternaNoDisponible)
async def _externa_no_disponible(_: Request, exc: ExternaNoDisponible):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# Cualquier excepción no prevista: 500 con un mensaje genérico y un código
# corto. El texto de la excepción (los de pymysql traen host y puerto de la
# base) y el traceback van sólo al log, con el mismo código, para encontrarlo
# en el journal con lo que la persona ve en el toast. No pisa a los handlers
# más específicos (ExternaNoDisponible, HTTPException): Starlette usa primero
# el de la clase más cercana. Después de mandar esta respuesta, Starlette
# re-lanza la excepción al servidor y uvicorn la loguea otra vez: es
# aceptable, el registro con el código es el de acá.
_log_errores = logging.getLogger("app.errores")


@app.exception_handler(Exception)
async def _error_interno(request: Request, exc: Exception):
    codigo = secrets.token_hex(3).upper()
    # exc_info explícito: no depender de que el handler corra dentro del
    # `except` de Starlette para que el traceback salga en el log.
    _log_errores.exception(
        "Error interno %s en %s %s", codigo, request.method, request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del sistema. Si se repite, avisá a sistemas con el código {codigo}"},
    )


# Comprime respuestas grandes (ej. /lineas de una quincena: ~1.3 MB de JSON
# que gzip baja a ~150 KB). Las chicas (<1 KB) no pagan el overhead.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
from app.core import auth, asistente, administracion  # noqa: E402
from app.core.auth import get_usuario_actual  # noqa: E402
from app.core.models import Usuario  # noqa: E402

app.include_router(auth.router)
app.include_router(administracion.router)
for modulo in activos():
    for r in modulo.routers:
        app.include_router(r)
app.include_router(asistente.router)


@app.get("/")
def root():
    return {"sistema": "Sistema de gestión La Asturiana", "version": "1.0.0"}


@app.get("/api/auth/modulos", tags=["Auth"])
def modulos_activos(usuario: Usuario = Depends(get_usuario_actual)):
    """Módulos activos del sistema, para el Inicio y la Administración."""
    return [m.publico() for m in activos()]


@app.get("/api/preliquidacion/generar/status")
def generar_status():
    """Endpoint liviano para verificar que el servidor sigue vivo durante generación."""
    return {"status": "ok"}


_log_health = logging.getLogger("app.health")


@app.get("/health")
def health():
    # Sólo estado y booleanos por HTTP: los textos de error (los de pymysql
    # traen host y puerto de la base) van al log, y los nombres de tablas y
    # columnas faltantes están en el banner de arranque; para el detalle,
    # mirar el journal.
    conexiones = verificar_conexiones()
    ok = conexiones["externa"] and conexiones["propia"]
    for err in conexiones["errores"]:
        _log_health.error("/health: %s", err)
    if getattr(app.state, "esquema_incompleto", False):
        _log_health.error(
            "/health: faltan tablas o columnas en la base propia (migraciones sin "
            "aplicar); los nombres están en el banner de arranque del journal",
        )
        status = "error"
    elif ok:
        status = "ok"
    else:
        status = "degraded"
    return {
        "status": status,
        "bd_sueldos": conexiones["sueldos"],
        "bd_externa": conexiones["externa"],
        "bd_propia": conexiones["propia"],
    }
