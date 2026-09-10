"""Identidad de una persona en el sistema: su CUIL (PR 5 de la etapa 0).

La tabla `usuarios` tiene `email UNIQUE NOT NULL` y no se migra: el usuario de
alguien dado de alta desde el padrón se guarda con un email **sintético**
derivado de su CUIL. Nadie lo tipea ni recibe correo ahí — el login acepta el
CUIL pelado y le pega el dominio. Quien tiene mail real (los usuarios previos
al PR 5) sigue entrando con su mail.
"""

DOMINIO_USUARIOS = "usuarios.laasturianasrl.com.ar"

LARGO_CUIL = 11


def normalizar_cuil(texto: str | None) -> str | None:
    """Deja solo los dígitos y devuelve el CUIL, o None si no son 11 dígitos.
    Acepta '20-11111111-9', '20 11111111 9' y '20111111119'."""
    digitos = "".join(c for c in (texto or "") if c.isdigit())
    return digitos if len(digitos) == LARGO_CUIL else None


def email_de_cuil(cuil: str) -> str:
    return f"{cuil}@{DOMINIO_USUARIOS}"


def cuil_de_email(email: str | None) -> str | None:
    """El CUIL de un email sintético; None si es un mail real."""
    sufijo = f"@{DOMINIO_USUARIOS}"
    if not email or not email.endswith(sufijo):
        return None
    return normalizar_cuil(email[: -len(sufijo)])
