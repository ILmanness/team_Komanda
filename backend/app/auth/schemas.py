from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    login: str = Field(min_length=3, max_length=40, pattern=r'^[a-zA-Z0-9_-]+$')


class LoginRequest(BaseModel):
    login: str | None = Field(default=None, min_length=3, max_length=320)
    email: EmailStr | None = None
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def require_identifier(self):
        if not self.login and not self.email:
            raise ValueError('Укажите логин или email')
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr | None
    login: str
    display_name: str
    role: str
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
