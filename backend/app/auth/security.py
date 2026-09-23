from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.auth_secret_key,
        algorithm=settings.hesh_alg,
    )


def decode_access_token(token: str) -> UUID:
    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.auth_secret_key,
        algorithms=[settings.hesh_alg],
    )

    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    user_id = payload.get("sub")

    if not user_id:
        raise ValueError("Token does not contain user id")

    return UUID(user_id)
