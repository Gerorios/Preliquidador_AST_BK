"""
Asistente de ayuda de USO del sistema.

Es un chat que le explica al liquidador cómo usar el sistema, apoyándose SOLO en
documentación (el glosario `CONTEXT.md` + la guía `docs/AYUDA.md`), que se le
"pega" al prompt del modelo (context-stuffing, sin RAG). No accede a la base ni
a datos reales: es ayuda de uso, no de datos.

El modelo se llama vía la API de OpenAI (GPT-4o mini por defecto). La API key
vive en el `.env` (`OPENAI_API_KEY`); si no está cargada, el endpoint responde
503 y la app sigue funcionando normalmente.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_usuario_actual
from app.core.config import settings
from app.models.models import Usuario

router = APIRouter(prefix="/api/asistente", tags=["Asistente"])

# Raíz del repo backend: app/api/asistente.py → app/ → api/ → raíz
_BASE_DIR = Path(__file__).resolve().parents[2]

# Documentación que forma el conocimiento del asistente, en orden.
_DOCS = ("CONTEXT.md", "docs/AYUDA.md")

_PREAMBULO = """\
Sos el asistente de ayuda del "Sistema de Preliquidación" de La Asturiana SRL.
Tu único trabajo es ayudar al liquidador a **usar el sistema**: explicarle cómo
hacer las cosas, qué significa cada término y dónde está cada función, usando la
documentación que aparece más abajo (un glosario y una guía de uso).

Reglas que tenés que cumplir siempre:

1. AYUDA DE USO, NO DE DATOS. No tenés acceso a la base ni a datos reales
   (sueldos, importes, líneas, liquidaciones de nadie). Nunca inventes ni
   afirmes un número o dato concreto de un empleado, cliente o quincena. Si te
   preguntan un dato real ("¿cuánto le pago a Juan?", "¿cuánto dio la quincena?"),
   aclará que no ves datos y decile en qué pantalla lo puede mirar él mismo.

2. NO tomás decisiones de liquidación ni das indicaciones de cuánto pagar. Solo
   explicás cómo se opera el sistema.

3. Basate SOLO en la documentación de abajo. Si algo no está cubierto ahí, decilo
   con honestidad ("eso no lo tengo documentado") y sugerí a quién consultar; no
   inventes pasos, botones ni pantallas que no figuren en la guía.

4. Escribí en español rioplatense, con un tono cálido y cercano, como un
   compañero que le explica a alguien que recién empieza. No te quedes en el
   paso mecánico: contá también el para qué y el porqué, en palabras simples.
   Si aparece un término del sistema (quincena, concepto común, reemplaza al
   común, línea incompleta, etc.), aclaralo la primera vez en lenguaje llano.
   Evitá la jerga y las respuestas telegráficas: preferí frases completas y,
   cuando ayude a entender, sumá un ejemplo corto. Igual, andá al grano: claro
   y explicativo, sin irte por las ramas ni escribir de más.

5. Cuando des un procedimiento, guialo paso a paso y nombrá los botones y
   pantallas TAL CUAL aparecen en la guía (por ejemplo: pestaña "Panel de
   precios", botón "▶ Generar / Actualizar"), pero acompañá cada paso con una
   frase corta que explique qué se logra, no solo qué apretar.

6. Cuando corresponda, recordale amablemente que verifique los datos en el
   sistema; sos una ayuda, no una fuente de verdad sobre los números.

Si el usuario te saluda o pregunta algo fuera del sistema, respondé con cortesía
y reconducí hacia en qué lo podés ayudar con el uso del sistema.
"""


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    """Arma el system prompt una sola vez (preámbulo + docs) y lo cachea."""
    partes = [_PREAMBULO]
    for nombre in _DOCS:
        ruta = _BASE_DIR / nombre
        if ruta.exists():
            contenido = ruta.read_text(encoding="utf-8")
            partes.append(f"\n\n========== {nombre} ==========\n\n{contenido}")
    return "\n".join(partes)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class MensajeChat(BaseModel):
    rol: Literal["user", "assistant"]
    contenido: str


class AsistenteRequest(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=2000)
    historial: list[MensajeChat] = Field(default_factory=list)
    pantalla: Optional[str] = None  # p. ej. "Panel de precios", "Revisión"


class AsistenteResponse(BaseModel):
    respuesta: str


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=AsistenteResponse)
def chat(
    datos: AsistenteRequest,
    usuario: Usuario = Depends(get_usuario_actual),
):
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="El asistente no está configurado (falta OPENAI_API_KEY en el .env).",
        )

    # Import perezoso: si el paquete no está instalado, solo falla este endpoint,
    # no el arranque de toda la app.
    try:
        from openai import OpenAI, OpenAIError
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="El asistente no está disponible (falta instalar el paquete 'openai').",
        )

    client = OpenAI(api_key=settings.openai_api_key)

    mensajes: list[dict] = [{"role": "system", "content": _system_prompt()}]
    # Historial acotado a las últimas vueltas para no crecer sin límite.
    for m in datos.historial[-12:]:
        mensajes.append({"role": m.rol, "content": m.contenido})

    contexto_pantalla = f"[El usuario está en la pantalla: {datos.pantalla}]\n\n" if datos.pantalla else ""
    mensajes.append({"role": "user", "content": contexto_pantalla + datos.pregunta})

    try:
        resp = client.chat.completions.create(
            model=settings.asistente_modelo,
            messages=mensajes,
            temperature=0.4,
            max_tokens=900,
        )
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"Error del asistente: {e}")

    respuesta = (resp.choices[0].message.content or "").strip()
    return AsistenteResponse(respuesta=respuesta)
