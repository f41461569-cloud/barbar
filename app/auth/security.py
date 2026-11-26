from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    to_encode: dict[str, Any] = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return {}
    return payload


def get_optional_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Resolve the logged-in user for server-rendered pages.

    The browser path is the HttpOnly ``access_token`` cookie (ADR 003); an
    ``Authorization: Bearer`` header is accepted as a fallback for API clients.
    This dependency is optional: anonymous requests and invalid/expired tokens
    return ``None`` instead of raising.
    """
    token = request.cookies.get("access_token") or ""
    if not token:
        scheme, _, credentials = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() == "bearer":
            token = credentials.strip()
    if not token:
        return None

    payload = decode_access_token(token)
    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        return None
    return db.get(User, user_id)
