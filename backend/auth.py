"""
Autenticación con JWT + contraseñas con hash (bcrypt).
El token se genera al hacer login y el frontend lo manda en cada
request como header: Authorization: Bearer <token>
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Nunca usar un valor fijo conocido de respaldo -- cualquiera que vea
    # este código (o el repositorio en GitHub) podría forjar tokens
    # válidos, incluso de administrador, si supiera cuál es el valor de
    # respaldo. Si JWT_SECRET no está configurado en el entorno (Render ->
    # Environment -> JWT_SECRET), se genera una clave aleatoria SOLO para
    # este arranque del servidor -- las sesiones existentes se cierran en
    # cada reinicio/deploy mientras falte configurarlo, pero nunca queda
    # un secreto adivinable de antemano.
    JWT_SECRET = secrets.token_urlsafe(48)
    print(
        "ADVERTENCIA: la variable de entorno JWT_SECRET no está configurada -- "
        "se generó una clave aleatoria SOLO para este arranque del servidor "
        "(las sesiones se cerrarán en el próximo reinicio/deploy). "
        "Configúrala en Render -> Environment -> JWT_SECRET con un valor fijo "
        "y secreto para que las sesiones sobrevivan reinicios."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRA_DIAS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, AttributeError):
        return False


def crear_token(usuario: dict) -> str:
    payload = {
        "id": usuario["id"],
        "username": usuario["username"],
        "nombre": usuario["nombre_completo"],
        "rol": usuario["rol"],
        "empresa_id": usuario.get("empresa_id"),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRA_DIAS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    token = authorization.split(" ", 1)[1]
    try:
        return verificar_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada, inicia sesión de nuevo")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
