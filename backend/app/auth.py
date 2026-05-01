"""JWT and password utilities."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "dev-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET", _DEFAULT_SECRET)

if SECRET_KEY == _DEFAULT_SECRET:
    logger.warning(
        "JWT_SECRET is not set — using insecure default. "
        "Set the JWT_SECRET environment variable in production."
    )
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
