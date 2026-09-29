from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.auth.security import (
    access_token_expires_at,
    access_token_hash,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.auth.dependencies import bearer_scheme
from app.db import engine

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


async def get_user_by_login(identifier: str):
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
                    updated_at,
                    password_hash
                FROM users
                WHERE LOWER(email) = LOWER(:identifier)
                   OR LOWER(login) = LOWER(:identifier)
                """
            ),
            {"identifier": identifier},
        )).mappings().first()

    return dict(result) if result else None


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest):
    email = str(data.email).lower()
    login_name = data.login.lower()

    existing_user = await get_user_by_login(email) or await get_user_by_login(login_name)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    hashed_password = hash_password(data.password)

    try:
        async with engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    INSERT INTO users (
                        email,
                        login,
                        password_hash,
                        display_name,
                        role
                    )
                    VALUES (
                        :email,
                        :login,
                        :password_hash,
                        :display_name,
                        'player'
                    )
                    RETURNING
                        id,
                        email,
                        login,
                        display_name,
                        role,
                        created_at,
                        updated_at
                    """
                ),
                {
                    "email": email,
                    "login": login_name,
                    "password_hash": hashed_password,
                    "display_name": data.display_name,
                },
            )

            user = dict(result.mappings().one())

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        ) from None

    access_token = create_access_token(user["id"])

    return AuthResponse(
        access_token=access_token,
        user=UserResponse(**user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login(data: LoginRequest):
    identifier = str(data.login or data.email).lower()

    user = await get_user_by_login(identifier)

    if user is None or not user["password_hash"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(
        data.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    public_user = {
        "id": user["id"],
        "email": user["email"],
        "login": user["login"],
        "display_name": user["display_name"],
        "role": user["role"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }

    access_token = create_access_token(user["id"])

    return AuthResponse(
        access_token=access_token,
        user=UserResponse(**public_user),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]):
    token = credentials.credentials
    try:
        decode_access_token(token)
        expires_at = access_token_expires_at(token)
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail='Invalid or expired token') from None
    async with engine.begin() as connection:
        await connection.execute(text('''
            INSERT INTO revoked_access_tokens (token_hash, expires_at)
            VALUES (:token_hash, :expires_at) ON CONFLICT (token_hash) DO NOTHING
        '''), {'token_hash': access_token_hash(token), 'expires_at': expires_at})
    return MessageResponse(
        message="Successfully logged out",
    )

