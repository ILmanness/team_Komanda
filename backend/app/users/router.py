from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserResponse
from app.db import engine

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    return current_user


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)

    @field_validator('display_name', mode='before')
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


@router.patch('/me', response_model=UserResponse)
def update_me(data: ProfileUpdate, current_user: Annotated[dict, Depends(get_current_user)]):
    with engine.begin() as connection:
        row = connection.execute(text('''
            UPDATE users SET display_name=:name, updated_at=now()
            WHERE id=:id
            RETURNING id, email, login, display_name, role, created_at, updated_at
        '''), {'id': current_user['id'], 'name': data.display_name}).mappings().one()
    return dict(row)


@router.get('/me/stats')
def get_my_stats(current_user: Annotated[dict, Depends(get_current_user)]):
    with engine.connect() as connection:
        row = connection.execute(text('''
            SELECT count(*) AS conversations,
                   count(*) FILTER (WHERE status='active') AS active,
                   count(*) FILTER (WHERE status='completed') AS finished,
                   count(*) FILTER (WHERE final_result->>'result'='success') AS successful,
                   count(*) FILTER (WHERE mode='method_training') AS trainings
            FROM game_sessions
            WHERE user_id=:user_id AND history_purged_at IS NULL
        '''), {'user_id': current_user['id']}).mappings().one()
        story_successes = connection.execute(text('''
            SELECT count(*) FROM story_mission_progress WHERE user_id=:user_id
        '''), {'user_id': current_user['id']}).scalar_one()
    return {**dict(row), 'story_successes': story_successes}
