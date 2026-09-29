import random
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.db import engine
from app.game.goal_tracker import GoalTracker
from app.game.hints import HintGenerator, hint_limit
from app.game.scoring import Scoring
from app.story_progress import get_story_progress

from .schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    FinishSessionResponse,
    SessionHintResponse,
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


async def _get_session(
    session_id: UUID,
    user_id: UUID,
):
    async with engine.connect() as connection:
        row = (await connection.execute(
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
                    config_snapshot,
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
        )).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    data = dict(row)
    snapshot = data.pop('config_snapshot') or {}
    mission = snapshot.get('mission') or {}
    character = snapshot.get('character') or {}
    return {**data, "ai_mode": 'none' if data['mode'] == 'method_training' else get_settings().ai_provider,
            'mission_title': mission.get('title'), 'mission_task': mission.get('task'),
            'mission_situation': (mission.get('context') or {}).get('situation'),
            'mission_public_context': (mission.get('context') or {}).get('public_context'),
            'character_name': character.get('name'), 'character_slug': character.get('slug'),
            'character_role_title': character.get('role_title'),
            'character_description': character.get('description'),
            'character_paei_description': character.get('paei_description'),
            'character_behavior_description': character.get('behavior_description')}


@router.get("", response_model=list[SessionListItem])
async def list_sessions(current_user: CurrentUser):
    async with engine.connect() as connection:
        rows = (await connection.execute(text("""
            SELECT s.id, s.mode, s.status, s.mission_id, m.title AS mission_title,
                   s.custom_context, s.state, s.final_result, s.started_at, s.last_activity_at
            FROM game_sessions AS s
            LEFT JOIN missions AS m ON m.id = s.mission_id
            WHERE s.user_id = :user_id AND s.history_purged_at IS NULL
            ORDER BY s.last_activity_at DESC
            LIMIT 30
        """), {"user_id": current_user["id"]})).mappings().all()
    return [SessionListItem(**dict(row)) for row in rows]


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
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

    async with engine.begin() as connection:

        mission = None

        if data.mode in ("story", "method_training"):

            mission = (await connection.execute(
                text(
                    """
                    SELECT
                        id,
                        character_id,
                        mission_type,
                        interaction_type,
                        storyline_id,
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
            )).mappings().first()

            if mission is None:
                raise HTTPException(
                    status_code=404,
                    detail="Published mission not found",
                )

            if data.mode == 'story':
                progress = await get_story_progress(connection, mission['storyline_id'], user_id)
                if not any(item['mission_id'] == mission['id'] and item['unlocked'] for item in progress):
                    raise HTTPException(status_code=403, detail='Complete the previous story mission first')

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

            character = (await connection.execute(
                text(
                    """
                    SELECT
                        id,
                        slug,
                        name,
                        role_title,
                        description,
                        base_prompt,
                        paei_profile_id,
                        paei_description,
                        behavior_description,
                        behavior
                    FROM characters
                    WHERE id = :id
                    """
                ),
                {
                    "id": character_id,
                },
            )).mappings().first()

            if character is None:
                raise HTTPException(
                    status_code=400,
                    detail="Character not found",
                )

        paei = None

        if data.paei_profile_id is not None:

            paei = (await connection.execute(
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
            )).mappings().first()

            if paei is None:
                raise HTTPException(
                    status_code=400,
                    detail="PAEI profile not found",
                )

        difficulty = None

        if data.difficulty_profile_id is not None:

            difficulty = (await connection.execute(
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
            )).mappings().first()

            if difficulty is None:
                raise HTTPException(
                    status_code=400,
                    detail="Difficulty profile not found",
                )

        if data.mode == 'method_training' and mission['interaction_type'] not in ('single_choice', 'guided_training', 'branching_training'):
            raise HTTPException(status_code=400, detail='Training requires authored answers')

        if data.mode == 'story' and character is not None and paei is None and character['paei_profile_id']:
            paei = (await connection.execute(text('''SELECT id, code, leading_letter, p_value,
                a_value, e_value, i_value, prompt_rules, behavior FROM paei_profiles WHERE id=:id'''),
                {'id': character['paei_profile_id']})).mappings().first()

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
        if mission is not None and mission['interaction_type'] == 'guided_training':
            guided = (mission['config'] or {}).get('guided') or {}
            initial_state = {'turn': 0, 'node_id': guided['start_node_id'], 'events': []}
        elif mission is not None and mission['interaction_type'] == 'branching_training':
            tool = (mission['config'] or {}).get('branching') or {}
            available = [item for item in tool.get('scenarios', []) if item.get('status') == 'active']
            if not available:
                raise HTTPException(status_code=422, detail='Training has no active scenarios')
            previous = (await connection.execute(text('''
                SELECT state->>'scenario_id' FROM game_sessions
                WHERE user_id=:user_id AND mission_id=:mission_id
                ORDER BY started_at DESC LIMIT 1
            '''), {'user_id': user_id, 'mission_id': data.mission_id})).scalar_one_or_none()
            alternatives = [item for item in available if item['id'] != previous]
            pool = alternatives or available
            scenario = random.choices(pool, weights=[item['weight'] for item in pool], k=1)[0]
            initial_state = {'turn': 0, 'scenario_id': scenario['id'],
                             'node_id': scenario['start_node_id'], 'events': []}
        elif data.mode == 'custom' or (mission is not None and mission['interaction_type'] == 'ai_dialogue'):
            scenario_goal = (
                data.custom_context.get('goal')
                if data.mode == 'custom'
                else mission['task'] if mission is not None else None
            )
            if isinstance(scenario_goal, str) and scenario_goal.strip():
                initial_state['goal_state'] = GoalTracker.initial(scenario_goal)

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
                "base_prompt": character["base_prompt"],
                "paei_description": character["paei_description"],
                "behavior_description": character["behavior_description"],
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

        session = (await connection.execute(
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
                "paei_profile_id": paei['id'] if paei is not None else None,
                "difficulty_profile_id": data.difficulty_profile_id,
                "mode": data.mode,
                "custom_context": Jsonb(data.custom_context) if data.custom_context is not None else None,
                "state": Jsonb(initial_state),
                "config_snapshot": Jsonb(config_snapshot),
            },
        )).mappings().one()

        opening_message = None

        if mission is not None:

            opening_message = mission_context.get(
                "opening_message"
            )

        if opening_message:

            await connection.execute(
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
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
):
    return await _get_session(
        session_id=session_id,
        user_id=current_user["id"],
    )


@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagesResponse,
)
async def get_session_messages(
    session_id: UUID,
    current_user: CurrentUser,
):
    await _get_session(
        session_id=session_id,
        user_id=current_user["id"],
    )

    async with engine.connect() as connection:

        rows = (await connection.execute(
            text(
                """
                SELECT
                    id,
                    session_id,
                    sequence_number,
                    role,
                    content,
                    CASE WHEN payload->>'emotion' IN ('neutral', 'warm', 'tense', 'angry')
                         THEN payload->>'emotion' ELSE 'neutral' END AS emotion,
                    processing_status,
                    created_at
                FROM session_messages
                WHERE session_id = :session_id
                ORDER BY sequence_number
                """
            ),
            {
                "session_id": session_id,
            },
        )).mappings().all()

    return SessionMessagesResponse(
        session_id=session_id,
        messages=[
            SessionMessageResponse(**dict(row))
            for row in rows
        ],
    )


@router.post(
    "/{session_id}/hint",
    response_model=SessionHintResponse,
)
async def request_hint(
    session_id: UUID,
    current_user: CurrentUser,
):
    """Issue one bounded, non-revealing hint for a completed active turn."""
    async with engine.begin() as connection:
        row = (await connection.execute(text("""
            SELECT status, state, config_snapshot
            FROM game_sessions
            WHERE id = :session_id AND user_id = :user_id
            FOR UPDATE
        """), {'session_id': session_id, 'user_id': current_user['id']})).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail='Session not found')
        if row['status'] != 'active':
            raise HTTPException(status_code=409, detail='Hints are unavailable after the game')

        pending = (await connection.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM session_messages
                WHERE session_id = :session_id
                  AND role = 'user'
                  AND processing_status = 'pending'
            )
        """), {'session_id': session_id})).scalar_one()
        if pending:
            raise HTTPException(status_code=409, detail='Wait for the current turn to finish')

        state = dict(row['state'] or {})
        turn = int(state.get('turn') or 0)
        if turn < 1:
            raise HTTPException(status_code=409, detail='Complete a turn before requesting a hint')
        if state.get('hint_last_turn') == turn:
            raise HTTPException(status_code=409, detail='Hint already used on this turn')

        snapshot = row['config_snapshot'] or {}
        difficulty = snapshot.get('difficulty') or {}
        limit = hint_limit(difficulty.get('code'))
        used = int(state.get('hints_used') or 0)
        if used >= limit:
            raise HTTPException(status_code=409, detail='Hint limit reached')

        evaluation = (await connection.execute(text("""
            SELECT evaluation
            FROM session_messages
            WHERE session_id = :session_id
              AND role = 'user'
              AND processing_status = 'completed'
            ORDER BY sequence_number DESC
            LIMIT 1
        """), {'session_id': session_id})).scalar_one_or_none()
        if not isinstance(evaluation, dict) or evaluation.get('schema_version') != 'ai10-v1':
            raise HTTPException(status_code=409, detail='No evaluated turn is available for a hint')

        mission = snapshot.get('mission') or {}
        hint = HintGenerator().generate(
            goal=mission.get('task') or '',
            evaluation=evaluation,
            state=state,
            level=min(used + 1, 3),
        )
        state['hints_used'] = used + 1
        state['hint_last_turn'] = turn
        state['negotiation_quality'] = max(
            0, int(state.get('negotiation_quality', 50)) - 3,
        )
        history = state.get('hint_history')
        state['hint_history'] = [
            *(history if isinstance(history, list) else []),
            {'turn': turn, 'hint_type': hint.hint_type, 'level': hint.level},
        ]
        state['score'] = Scoring().calculate(state=state)['score']
        await connection.execute(text("""
            UPDATE game_sessions
            SET state = :state, lock_version = lock_version + 1,
                last_activity_at = now()
            WHERE id = :session_id AND user_id = :user_id
        """), {
            'state': Jsonb(state),
            'session_id': session_id,
            'user_id': current_user['id'],
        })

    return SessionHintResponse(
        **hint.model_dump(),
        hints_used=used + 1,
        remaining=limit - used - 1,
    )


@router.post(
    "/{session_id}/finish",
    response_model=FinishSessionResponse,
)
async def finish_session(
    session_id: UUID,
    current_user: CurrentUser,
):
    async with engine.begin() as connection:

        session = (await connection.execute(
            text(
                """
                SELECT
                    id,
                    mode,
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
        )).mappings().first()

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
            "result": "finished" if session["mode"] == "custom" else "failure",
            "reason": "user_finished",
            "completed_by": "player",
        }

        updated = (await connection.execute(
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
        )).mappings().one()

    return FinishSessionResponse(**dict(updated))
