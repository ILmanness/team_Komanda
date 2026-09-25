from fastapi import APIRouter, HTTPException, status
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
    create_access_token,
    hash_password,
    verify_password,
)
from app.db import engine

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


def get_user_by_login(identifier: str):
    with engine.connect() as connection:
        result = connection.execute(
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
        ).mappings().first()

    return dict(result) if result else None


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    email = str(data.email).lower()
    login_name = data.login.lower()

    existing_user = get_user_by_login(email) or get_user_by_login(login_name)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    hashed_password = hash_password(data.password)

    try:
        with engine.begin() as connection:
            result = connection.execute(
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
def login(data: LoginRequest):
    identifier = str(data.login or data.email).lower()

    user = get_user_by_login(identifier)

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
def logout():
    return MessageResponse(
        message="Successfully logged out",
    )

