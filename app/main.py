import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# En Windows, sin PYTHONIOENCODING/PYTHONUTF8, stdout/stderr usan el codepage
# de la consola (p. ej. cp1252), que no soporta los caracteres Unicode que
# usan los prints de abajo. Sin esto, el lifespan revienta con
# UnicodeEncodeError al arrancar y el servidor nunca queda arriba.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings
from app.core.database import verificar_conexiones, engine_propia, Base
from app.models import models  # noqa: F401 — registra todos los modelos


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("─" * 50)
    print("  Sistema de Preliquidación — La Asturiana SRL")
    print("─" * 50)

    resultado = verificar_conexiones()
    print(f"  BD sueldos:  {'✓ OK' if resultado['sueldos'] else '✗ ERROR'}")
    print(f"  BD externa:  {'✓ OK' if resultado['externa'] else '✗ ERROR'}")
    print(f"  BD propia:   {'✓ OK' if resultado['propia'] else '✗ ERROR'}")

    if resultado["errores"]:
        for err in resultado["errores"]:
            print(f"  ERROR: {err}")

    if resultado["propia"]:
        # Crea solo las tablas que NO existen — nunca toca las existentes
        Base.metadata.create_all(bind=engine_propia, checkfirst=True)
        print("  Tablas BD propia: verificadas")

    print("─" * 50)
    yield
    print("Servidor detenido.")


app = FastAPI(
    title="Sistema de Preliquidación — La Asturiana SRL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
from app.api import preliquidacion, precios, auth, export, asistente  # noqa: E402
app.include_router(auth.router)
app.include_router(preliquidacion.router)
app.include_router(precios.router)
app.include_router(export.router)
app.include_router(asistente.router)


@app.get("/")
def root():
    return {"sistema": "Preliquidación La Asturiana", "version": "1.0.0"}


@app.get("/api/preliquidacion/generar/status")
def generar_status():
    """Endpoint liviano para verificar que el servidor sigue vivo durante generación."""
    return {"status": "ok"}


@app.get("/health")
def health():
    conexiones = verificar_conexiones()
    ok = conexiones["externa"] and conexiones["propia"]
    return {
        "status": "ok" if ok else "degraded",
        "bd_externa": conexiones["externa"],
        "bd_propia": conexiones["propia"],
        "errores": conexiones["errores"],
    }
