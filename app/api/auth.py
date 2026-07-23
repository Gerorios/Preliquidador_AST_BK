import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.database import get_db_propia
from app.models.models import Usuario

router = APIRouter(prefix="/api/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: dict


class UsuarioMe(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def verificar_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def crear_token(data: dict) -> str:
    payload = data.copy()
    # python-jose exige que el claim "sub" sea string (spec JWT).
    # Si se pasa un int (ej. usuario.id) sin convertir, jwt.decode()
    # lanza JWTClaimsError ("Subject must be a string") y el endpoint
    # devuelve 401 SIEMPRE, sin importar si el token es válido.
    if "sub" in payload:
        payload["sub"] = str(payload["sub"])
    payload["exp"] = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


# Cache de proceso del usuario autenticado: la base está remota (~200ms por
# query) y cada request autenticado pagaba un SELECT de usuarios. Con TTL
# corto: desactivar un usuario tarda hasta _USUARIO_CACHE_TTL segundos en
# cortar sus requests (el token JWT ya duraba horas, así que la ventana real
# de revocación no empeora en la práctica).
_USUARIO_CACHE: dict[int, tuple[Usuario, float]] = {}
_USUARIO_CACHE_TTL = 60  # segundos


def invalidar_cache_usuarios():
    _USUARIO_CACHE.clear()


def get_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db_propia),
) -> Usuario:
    credenciales_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        sub = payload.get("sub")
        if sub is None:
            raise credenciales_exc
        user_id = int(sub)  # el claim viene como string, se reconvierte a int para la query
    except (JWTError, ValueError):
        raise credenciales_exc

    en_cache = _USUARIO_CACHE.get(user_id)
    if en_cache and en_cache[1] > time.monotonic():
        return en_cache[0]

    usuario = db.query(Usuario).filter(
        Usuario.id == user_id,
        Usuario.activo == True,
    ).first()

    if not usuario:
        _USUARIO_CACHE.pop(user_id, None)
        raise credenciales_exc

    # Se desliga de la sesión para que sobreviva al cierre de esta request
    # (los atributos ya están cargados; solo se leen id/nombre/email/rol).
    db.expunge(usuario)
    _USUARIO_CACHE[user_id] = (usuario, time.monotonic() + _USUARIO_CACHE_TTL)
    return usuario


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_propia),
):
    usuario = db.query(Usuario).filter(
        Usuario.email == form.username,
        Usuario.activo == True,
    ).first()

    if not usuario or not verificar_password(form.password, usuario.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    token = crear_token({"sub": usuario.id})

    return TokenResponse(
        access_token=token,
        usuario={
            "id": usuario.id,
            "nombre": usuario.nombre,
            "email": usuario.email,
            "rol": usuario.rol,
        }
    )


@router.get("/me", response_model=UsuarioMe)
def me(usuario: Usuario = Depends(get_usuario_actual)):
    return UsuarioMe(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
    )


@router.post("/logout")
def logout():
    # JWT es stateless — el logout lo maneja el frontend borrando el token
    return {"mensaje": "Sesión cerrada"}