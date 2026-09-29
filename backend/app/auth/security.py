from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import hashlib

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
        "jti": str(uuid4()),
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


def access_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def access_token_expires_at(token: str) -> datetime:
    settings = get_settings()
    payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.hesh_alg])
    if payload.get('type') != 'access':
        raise ValueError('Invalid token type')
    return datetime.fromtimestamp(payload['exp'], UTC)
