"""Autenticación: login, token JWT y el usuario autenticado (get_usuario_actual).
La autorización por módulo (quién puede operar qué) vive en
app/core/permisos.py y en permisos.py de cada módulo."""
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from typing import Optional

from app.core.config import settings
from app.core.database import get_db_propia
from app.core.identidad import cuil_de_email, email_de_cuil, normalizar_cuil
from app.core.models import Usuario

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
    modulos: dict[str, str]


class CambioPassword(BaseModel):
    actual: str
    nueva: str = Field(min_length=8)


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
    # (id/nombre/email/rol/modulos, cargados por selectin).
    db.expunge(usuario)
    _USUARIO_CACHE[user_id] = (usuario, time.monotonic() + _USUARIO_CACHE_TTL)
    return usuario


def _usuario_por_identificador(db: Session, tipeado: str) -> Optional[Usuario]:
    """Resuelve lo que la persona escribió en el campo usuario: un mail real, el
    email sintético completo, o el CUIL pelado (con o sin guiones)."""
    usuario = db.query(Usuario).filter(
        Usuario.email == tipeado, Usuario.activo == True  # noqa: E712
    ).first()
    if usuario:
        return usuario
    cuil = normalizar_cuil(tipeado)
    if not cuil:
        return None
    return db.query(Usuario).filter(
        Usuario.email == email_de_cuil(cuil), Usuario.activo == True  # noqa: E712
    ).first()


def _password_es_la_inicial(usuario: Usuario) -> bool:
    """True si la contraseña sigue siendo el CUIL con el que se dio de alta.
    Se calcula contra el hash guardado (no contra lo tipeado), así da igual si
    entró escribiendo el CUIL con guiones. El frontend lo usa para el aviso no
    bloqueante; nadie queda impedido de trabajar por esto."""
    cuil = cuil_de_email(usuario.email)
    return bool(cuil) and verificar_password(cuil, usuario.password)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_propia),
):
    usuario = _usuario_por_identificador(db, form.username)

    if not usuario or not verificar_password(form.password, usuario.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    token = crear_token({"sub": usuario.id})

    # Import local: app.core.permisos importa get_usuario_actual de este
    # módulo a nivel de módulo, así que un import arriba de auth.py crearía
    # un ciclo.
    from app.core.permisos import modulos_de

    return TokenResponse(
        access_token=token,
        usuario={
            "id": usuario.id,
            "nombre": usuario.nombre,
            "email": usuario.email,
            "rol": usuario.rol,
            "modulos": modulos_de(usuario),
            "password_inicial": _password_es_la_inicial(usuario),
        }
    )


@router.get("/me", response_model=UsuarioMe)
def me(usuario: Usuario = Depends(get_usuario_actual)):
    # Import local: ver comentario en login().
    from app.core.permisos import modulos_de

    return UsuarioMe(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        modulos=modulos_de(usuario),
    )


@router.post("/logout")
def logout():
    # JWT es stateless — el logout lo maneja el frontend borrando el token
    return {"mensaje": "Sesión cerrada"}


@router.post("/password")
def cambiar_password(
    datos: CambioPassword,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db_propia),
):
    """Cambio voluntario de la propia contraseña. Pide la actual: si alguien
    deja la sesión abierta, un tercero no puede quedarse con la cuenta."""
    # El usuario del cache está desligado de la sesión: se relee para escribir.
    actual = db.query(Usuario).filter(Usuario.id == usuario.id).first()
    if not actual or not verificar_password(datos.actual, actual.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta",
        )
    actual.password = pwd_context.hash(datos.nueva)
    db.commit()
    invalidar_cache_usuarios()
    return {"mensaje": "Contraseña actualizada"}