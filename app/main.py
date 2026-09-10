import sys
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# En Windows, sin PYTHONIOENCODING/PYTHONUTF8, stdout/stderr usan el codepage
# de la consola (p. ej. cp1252), que no soporta los caracteres Unicode que
# usan los prints de abajo. Sin esto, el lifespan revienta con
# UnicodeEncodeError al arrancar y el servidor nunca queda arriba.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import importlib

from sqlalchemy import inspect

from app.core.config import settings
from app.core.database import verificar_conexiones, engine_propia, Base
from app.core import models as models_core   # noqa: F401 — registra las tablas del núcleo (usuarios)
from app.modulos import activos

# Registra los modelos de cada módulo activo (ADR-0013): el núcleo no importa
# módulos por nombre, recorre el registro. Los inactivos no aportan tablas al
# chequeo de tablas faltantes de más abajo.
for _modulo in activos():
    if _modulo.modelos:
        importlib.import_module(_modulo.modelos)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("─" * 50)
    print("  Sistema de gestión — La Asturiana SRL")
    print("─" * 50)

    resultado = verificar_conexiones()
    print(f"  BD sueldos:  {'✓ OK' if resultado['sueldos'] else '✗ ERROR'}")
    print(f"  BD externa:  {'✓ OK' if resultado['externa'] else '✗ ERROR'}")
    print(f"  BD propia:   {'✓ OK' if resultado['propia'] else '✗ ERROR'}")

    if resultado["errores"]:
        for err in resultado["errores"]:
            print(f"  ERROR: {err}")

    # El esquema lo gobiernan las migraciones SQL (migrations/<modulo>/). No se
    # crean tablas al arrancar: una tabla que falta es un deploy incompleto.
    # No se aborta el arranque (systemd entraría en bucle de reinicios): se
    # imprime bien visible y se expone en /health para que se note enseguida.
    app.state.tablas_faltantes = []
    if resultado["propia"]:
        existentes = set(inspect(engine_propia).get_table_names())
        faltantes = sorted(t for t in Base.metadata.tables if t not in existentes)
        if faltantes:
            print(f"  ERROR: faltan tablas en la base propia (migraciones sin aplicar): {', '.join(faltantes)}")
            app.state.tablas_faltantes = faltantes
        else:
            print("  Tablas BD propia: verificadas")

    print("─" * 50)
    yield
    print("Servidor detenido.")


app = FastAPI(
    title="Sistema de gestión — La Asturiana SRL",
    version="1.0.0",
    lifespan=lifespan,
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


@app.get("/health")
def health():
    conexiones = verificar_conexiones()
    ok = conexiones["externa"] and conexiones["propia"]
    tablas_faltantes = getattr(app.state, "tablas_faltantes", [])
    if tablas_faltantes:
        status = "error"
    elif ok:
        status = "ok"
    else:
        status = "degraded"
    return {
        "status": status,
        "bd_externa": conexiones["externa"],
        "bd_propia": conexiones["propia"],
        "errores": conexiones["errores"],
        "tablas_faltantes": tablas_faltantes,
    }
