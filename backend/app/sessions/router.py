from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.db import engine

from .schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    FinishSessionResponse,
    SessionListItem,
    SessionMessageResponse,
    SessionMessagesResponse,
    SessionResponse,
)

router = APIRouter(
    prefix="/api/v1/sessions",
    tags=["sessions"],
)
CurrentUser = Annotated[dict, Depends(get_current_user)]


def _get_session(
    session_id: UUID,
    user_id: UUID,
):
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    mission_id,
                    character_id,
                    paei_profile_id,
                    difficulty_profile_id,
                    mode,
                    status,
                    state,
                    custom_context,
                    final_result,
                    started_at,
                    last_activity_at,
                    completed_at
                FROM game_sessions
                WHERE id = :session_id
                  AND user_id = :user_id
                """
            ),
            {
                "session_id": session_id,
                "user_id": user_id,
            },
        ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {**dict(row), "ai_mode": get_settings().ai_provider}


@router.get("", response_model=list[SessionListItem])
def list_sessions(current_user: CurrentUser):
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT s.id, s.mode, s.status, s.mission_id, m.title AS mission_title,
                   s.custom_context, s.state, s.started_at, s.last_activity_at
            FROM game_sessions AS s
            LEFT JOIN missions AS m ON m.id = s.mission_id
            WHERE s.user_id = :user_id AND s.history_purged_at IS NULL
            ORDER BY s.last_activity_at DESC
            LIMIT 30
        """), {"user_id": current_user["id"]}).mappings().all()
    return [SessionListItem(**dict(row)) for row in rows]


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    data: CreateSessionRequest,
    current_user: CurrentUser,
):
    user_id = current_user["id"]

    if data.mode in ("story", "method_training"):
        if data.mission_id is None:
            raise HTTPException(
                status_code=400,
                detail="mission_id is required for this session mode",
            )

        if data.custom_context is not None:
            raise HTTPException(
                status_code=400,
                detail="custom_context is allowed only for custom sessions",
            )

    if data.mode == "custom":
        if data.mission_id is not None:
            raise HTTPException(
                status_code=400,
                detail="mission_id must be null for custom sessions",
            )

        if not data.custom_context:
            raise HTTPException(
                status_code=400,
                detail="custom_context is required for custom sessions",
            )

    with engine.begin() as connection:

        mission = None

        if data.mode in ("story", "method_training"):

            mission = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        character_id,
                        mission_type,
                        title,
                        context,
                        task,
                        config
                    FROM missions
                    WHERE id = :mission_id
                      AND mission_type = :mode
                      AND status = 'published'
                    """
                ),
                {
                    "mission_id": data.mission_id,
                    "mode": data.mode,
                },
            ).mappings().first()

            if mission is None:
                raise HTTPException(
                    status_code=404,
                    detail="Published mission not found",
                )

        character_id = data.character_id

        if mission is not None:

            if character_id is None:
                character_id = mission["character_id"]

            if character_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="Mission has no character",
                )

        character = None

        if character_id is not None:

            character = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        slug,
                        name,
                        role_title,
                        description,
                        behavior
                    FROM characters
                    WHERE id = :id
                    """
                ),
                {
                    "id": character_id,
                },
            ).mappings().first()

            if character is None:
                raise HTTPException(
                    status_code=400,
                    detail="Character not found",
                )

        paei = None

        if data.paei_profile_id is not None:

            paei = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        code,
                        leading_letter,
                        p_value,
                        a_value,
                        e_value,
                        i_value,
                        prompt_rules,
                        behavior
                    FROM paei_profiles
                    WHERE id = :id
                    """
                ),
                {
                    "id": data.paei_profile_id,
                },
            ).mappings().first()

            if paei is None:
                raise HTTPException(
                    status_code=400,
                    detail="PAEI profile not found",
                )

        difficulty = None

        if data.difficulty_profile_id is not None:

            difficulty = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        code,
                        title,
                        prompt_rules,
                        settings
                    FROM difficulty_profiles
                    WHERE id = :id
                    """
                ),
                {
                    "id": data.difficulty_profile_id,
                },
            ).mappings().first()

            if difficulty is None:
                raise HTTPException(
                    status_code=400,
                    detail="Difficulty profile not found",
                )

        if data.mode in ("story", "method_training"):

            if paei is None:
                raise HTTPException(
                    status_code=400,
                    detail="paei_profile_id is required",
                )

            if difficulty is None:
                raise HTTPException(
                    status_code=400,
                    detail="difficulty_profile_id is required",
                )

        mission_context = {}

        if mission is not None:
            mission_context = mission["context"] or {}

        difficulty_settings = {}

        if difficulty is not None:
            difficulty_settings = difficulty["settings"] or {}

        initial_state = {
            "turn": 0,
            "contact": 0,
            "tension": 0,
            "progress": 0,
            "critical_errors": 0,
        }

        config_snapshot = {
            "mode": data.mode,
            "mission": None,
            "character": None,
            "paei": None,
            "difficulty": None,
            "rules": difficulty_settings,
        }

        if mission is not None:

            config_snapshot["mission"] = {
                "id": str(mission["id"]),
                "title": mission["title"],
                "context": mission["context"] or {},
                "task": mission["task"],
                "config": mission["config"] or {},
            }

        if character is not None:

            config_snapshot["character"] = {
                "id": str(character["id"]),
                "slug": character["slug"],
                "name": character["name"],
                "role_title": character["role_title"],
                "description": character["description"],
                "behavior": character["behavior"] or {},
            }

        if paei is not None:

            config_snapshot["paei"] = {
                "id": str(paei["id"]),
                "code": paei["code"],
                "leading_letter": paei["leading_letter"],
                "p_value": paei["p_value"],
                "a_value": paei["a_value"],
                "e_value": paei["e_value"],
                "i_value": paei["i_value"],
                "prompt_rules": paei["prompt_rules"],
                "behavior": paei["behavior"] or {},
            }

        if difficulty is not None:

            config_snapshot["difficulty"] = {
                "id": str(difficulty["id"]),
                "code": difficulty["code"],
                "title": difficulty["title"],
                "prompt_rules": difficulty["prompt_rules"],
                "settings": difficulty["settings"] or {},
            }

        if data.mode == "custom":

            config_snapshot["custom"] = {
                "context": data.custom_context,
            }

        session = connection.execute(
            text(
                """
                INSERT INTO game_sessions (
                    user_id,
                    mission_id,
                    character_id,
                    paei_profile_id,
                    difficulty_profile_id,
                    mode,
                    status,
                    custom_context,
                    state,
                    config_snapshot,
                    prompt_version
                )
                VALUES (
                    :user_id,
                    :mission_id,
                    :character_id,
                    :paei_profile_id,
                    :difficulty_profile_id,
                    :mode,
                    'active',
                    :custom_context,
                    :state,
                    :config_snapshot,
                    'v1'
                )
                RETURNING
                    id,
                    mode,
                    status,
                    mission_id,
                    character_id,
                    paei_profile_id,
                    difficulty_profile_id,
                    state,
                    started_at
                """
            ),
            {
                "user_id": user_id,
                "mission_id": data.mission_id,
                "character_id": character_id,
                "paei_profile_id": data.paei_profile_id,
                "difficulty_profile_id": data.difficulty_profile_id,
                "mode": data.mode,
                "custom_context": Jsonb(data.custom_context) if data.custom_context is not None else None,
                "state": Jsonb(initial_state),
                "config_snapshot": Jsonb(config_snapshot),
            },
        ).mappings().one()

        opening_message = None

        if mission is not None:

            opening_message = mission_context.get(
                "opening_message"
            )

        if opening_message:

            connection.execute(
                text(
                    """
                    INSERT INTO session_messages (
                        session_id,
                        sequence_number,
                        role,
                        content,
                        payload,
                        processing_status
                    )
                    VALUES (
                        :session_id,
                        1,
                        'assistant',
                        :content,
                        '{}',
                        'completed'
                    )
                    """
                ),
                {
                    "session_id": session["id"],
                    "content": opening_message,
                },
            )

    return CreateSessionResponse(**dict(session))


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
)
def get_session(
    session_id: UUID,
    current_user: CurrentUser,
):
    return _get_session(
        session_id=session_id,
        user_id=current_user["id"],
    )


@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagesResponse,
)
def get_session_messages(
    session_id: UUID,
    current_user: CurrentUser,
):
    _get_session(
        session_id=session_id,
        user_id=current_user["id"],
    )

    with engine.connect() as connection:

        rows = connection.execute(
            text(
                """
                SELECT
                    id,
                    session_id,
                    sequence_number,
                    role,
                    content,
                    payload,
                    evaluation,
                    processing_status,
                    reply_to_message_id,
                    error_code,
                    model,
                    token_count,
                    created_at
                FROM session_messages
                WHERE session_id = :session_id
                ORDER BY sequence_number
                """
            ),
            {
                "session_id": session_id,
            },
        ).mappings().all()

    return SessionMessagesResponse(
        session_id=session_id,
        messages=[
            SessionMessageResponse(**dict(row))
            for row in rows
        ],
    )


@router.post(
    "/{session_id}/finish",
    response_model=FinishSessionResponse,
)
def finish_session(
    session_id: UUID,
    current_user: CurrentUser,
):
    with engine.begin() as connection:

        session = connection.execute(
            text(
                """
                SELECT
                    id,
                    status,
                    final_result,
                    completed_at
                FROM game_sessions
                WHERE id = :session_id
                  AND user_id = :user_id
                FOR UPDATE
                """
            ),
            {
                "session_id": session_id,
                "user_id": current_user["id"],
            },
        ).mappings().first()

        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

        if session["status"] != "active":

            return FinishSessionResponse(
                id=session["id"],
                status=session["status"],
                final_result=session["final_result"],
                completed_at=session["completed_at"],
            )

        final_result = {
            "reason": "user_finished",
            "completed_by": "player",
        }

        updated = connection.execute(
            text(
                """
                UPDATE game_sessions
                SET
                    status = 'completed',
                    completed_at = now(),
                    last_activity_at = now(),
                    final_result = :final_result,
                    lock_version = lock_version + 1
                WHERE id = :session_id
                  AND user_id = :user_id
                  AND status = 'active'
                RETURNING
                    id,
                    status,
                    final_result,
                    completed_at
                """
            ),
            {
                "session_id": session_id,
                "user_id": current_user["id"],
                "final_result": Jsonb(final_result),
            },
        ).mappings().one()

    return FinishSessionResponse(**dict(updated))
