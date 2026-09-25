from uuid import UUID

import jwt
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import ValidationError
from sqlalchemy import text

from app.db import engine
from app.game.service import GameService

from .schemas import PlayerChoice, PlayerMessage

game_service = GameService()


router = APIRouter(
    tags=["game websocket"],
)


def get_user_id_from_websocket(
    websocket: WebSocket,
) -> UUID | None:

    token = websocket.query_params.get(
        "token"
    )

    if not token:
        return None

    try:
        from app.auth.security import (
            decode_access_token,
        )

        return decode_access_token(token)

    except (jwt.PyJWTError, ValueError):
        return None


def get_session(
    session_id: UUID,
    user_id: UUID,
):
    """
    Получение сессии для WebSocket handshake.
    """

    with engine.connect() as connection:

        row = connection.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    status,
                    state,
                    memory_summary,
                    config_snapshot,
                    lock_version,
                    last_processed_sequence
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

    return dict(row) if row else None


@router.websocket(
    "/api/v1/ws/sessions/{session_id}"
)
async def session_websocket(
    websocket: WebSocket,
    session_id: UUID,
):

    user_id = get_user_id_from_websocket(websocket)
    if user_id is None:
        await websocket.close(code=1008)
        return

    session = get_session(session_id=session_id, user_id=user_id)
    if session is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()


    session = get_session(
        session_id=session_id,
        user_id=user_id,
    )

    if session is None:

        await websocket.send_json(
            {
                "type": "error",
                "code": "session_not_found",
                "message": "Session not found",
            }
        )

        await websocket.close(
            code=1008
        )

        return

    await websocket.send_json(
        {
            "type": "session.connected",
            "session_id": str(session_id),
            "state": session["state"],
            "session_status": session["status"],
        }
    )

    try:

        while True:

            raw_message = (
                await websocket.receive_json()
            )

            try:

                is_choice = raw_message.get('type') == 'player.choice' if isinstance(raw_message, dict) else False
                message = (PlayerChoice if is_choice else PlayerMessage).model_validate(raw_message)

            except ValidationError as exc:

                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_message",
                        "message": str(exc),
                    }
                )

                continue

            session = get_session(
                session_id=session_id,
                user_id=user_id,
            )

            if session is None:

                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "session_not_found",
                        "message": "Session not found",
                    }
                )

                break

            if session["status"] != "active":

                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "session_not_active",
                        "message": "Session is not active",
                    }
                )

                continue

            content = message.content if not is_choice else None
            evaluation_override = None
            response_override = None
            if is_choice:
                config = (session['config_snapshot'] or {}).get('mission') or {}
                if config.get('config', {}).get('training') is None:
                    await websocket.send_json({'type': 'error', 'code': 'choice_unavailable',
                                               'message': 'This mission does not offer answer choices'})
                    continue
                choices = config['config']['training'].get('choices', [])
                choice = next((item for item in choices if item['id'] == message.choice_id), None)
                if choice is None:
                    await websocket.send_json({'type': 'error', 'code': 'invalid_choice',
                                               'message': 'Answer choice not found'})
                    continue
                content = choice['text']
                response_override = choice['feedback']
                evaluation_override = {
                    'intent': 'proposal', 'quality': choice['quality'],
                    'critical_error': choice['critical_error'], 'reason': choice['feedback'],
                    'effects': {key: choice[key] for key in ('contact', 'tension', 'progress')},
                }

            try:

                result = (
                    await game_service.process_player_message(
                        session_id=session_id,
                        user_id=user_id,
                        content=content,
                        idempotency_key=(
                            message.idempotency_key
                        ),
                        evaluation_override=evaluation_override,
                        response_override=response_override,
                    )
                )

                for event in result.get(
                    "events",
                    [],
                ):
                    await websocket.send_json(
                        event
                    )

            except Exception:  # noqa: BLE001 - keep the socket usable after a game service failure

                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "message_processing_failed",
                        "message": (
                            "Failed to process "
                            "player message"
                        ),
                    }
                )

    except WebSocketDisconnect:
        return
