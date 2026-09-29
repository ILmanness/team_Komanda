from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import text

from app.auth.security import access_token_hash, decode_access_token
from app.db import engine

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> UUID:
    token = credentials.credentials

    try:
        user_id = decode_access_token(token)
        async with engine.connect() as connection:
            revoked = (await connection.execute(text(
                'SELECT 1 FROM revoked_access_tokens WHERE token_hash=:token_hash'
            ), {'token_hash': access_token_hash(token)})).scalar()
        if revoked:
            raise ValueError('Revoked token')
        return user_id
    except (InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def get_current_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    async with engine.connect() as connection:
        result = (await connection.execute(
            text(
                """
                SELECT
                    id,
                    email,
                    login,
                    display_name,
                    role,
                    created_at,
                    updated_at
                FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        )).mappings().first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(result)
