"""Login simple con usuario/contrasena de .env y token JWT."""
import datetime
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "carneselrey123")
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # una semana

_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _constant_time_equals(a: str, b: str) -> bool:
    """Comparacion en tiempo constante para evitar timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


def _create_token() -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=TOKEN_EXPIRE_HOURS
    )
    payload = {"sub": ADMIN_USER, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Valida credenciales y devuelve un JWT."""
    user_ok = _constant_time_equals(body.username, ADMIN_USER)
    pass_ok = _constant_time_equals(body.password, ADMIN_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contrasena incorrectos",
        )
    return TokenResponse(access_token=_create_token())


def require_admin(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Dependency: protege endpoints de administracion. Valida el JWT."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticacion",
        )
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
        )
    return payload.get("sub", ADMIN_USER)
