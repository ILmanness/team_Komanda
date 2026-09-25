from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    mode: str = Field(
        ...,
        pattern="^(story|method_training|custom)$",
    )

    mission_id: UUID | None = None

    character_id: UUID | None = None

    paei_profile_id: UUID | None = None

    difficulty_profile_id: UUID | None = None

    custom_context: dict[str, Any] | None = None


class CreateSessionResponse(BaseModel):
    id: UUID
    mode: str
    status: str
    mission_id: UUID | None = None
    character_id: UUID | None = None
    paei_profile_id: UUID | None = None
    difficulty_profile_id: UUID | None = None
    state: dict[str, Any]
    started_at: datetime


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID

    mission_id: UUID | None = None
    character_id: UUID | None = None
    paei_profile_id: UUID | None = None
    difficulty_profile_id: UUID | None = None

    mode: str
    status: str

    state: dict[str, Any]
    custom_context: dict[str, Any] | None = None

    final_result: dict[str, Any] | None = None
    ai_mode: str

    started_at: datetime
    last_activity_at: datetime
    completed_at: datetime | None = None


class SessionListItem(BaseModel):
    id: UUID
    mode: str
    status: str
    mission_id: UUID | None = None
    mission_title: str | None = None
    custom_context: dict[str, Any] | None = None
    state: dict[str, Any]
    started_at: datetime
    last_activity_at: datetime


class SessionMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    sequence_number: int

    role: str
    content: str

    processing_status: str
    created_at: datetime


class SessionMessagesResponse(BaseModel):
    session_id: UUID
    messages: list[SessionMessageResponse]


class FinishSessionResponse(BaseModel):
    id: UUID
    status: str
    final_result: dict[str, Any] | None = None
    completed_at: datetime


class PlayerMessage(BaseModel):
    type: str = Field(
        default="player.message",
        pattern="^player\\.message$",
    )

    idempotency_key: UUID

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )


class PlayerChoice(BaseModel):
    type: str = Field(pattern=r'^player\.choice$')
    idempotency_key: UUID
    choice_id: str = Field(min_length=1, max_length=40)


class WebSocketError(BaseModel):
    type: str = "error"
    code: str
    message: str


class WebSocketMessageResponse(BaseModel):
    type: str
    message_id: UUID | None = None
    sequence_number: int | None = None
    content: str | None = None
    state: dict[str, Any] | None = None
    session_status: str | None = None
