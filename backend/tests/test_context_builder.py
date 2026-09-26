"""AI-05 context must be bounded, deterministic and safe for public projection."""

import json
from datetime import UTC, datetime
from uuid import UUID

from app.game.context_builder import ContextBuilder
from app.game.service import GameService
from app.sessions.schemas import SessionMessageResponse


def test_private_context_keeps_hidden_facts_but_public_projection_does_not():
    builder = ContextBuilder(max_history_messages=2, max_history_chars=100)
    session = {
        'id': 'session-1', 'mode': 'story', 'status': 'active',
        'state': {'turn': 2, 'contact': 70, 'tension': 30, 'progress': 20},
    }
    mission = {
        'id': 'mission-1', 'title': 'Переговоры', 'task': 'Согласовать срок',
        'context': {
            'public_context': 'Коллега задерживает задачу',
            'hidden_context': 'Секрет: он не понял требования',
            'npc_interests': ['сохранить репутацию'],
        },
    }
    character = {
        'id': 'character-1', 'name': 'Игорь', 'role_title': 'коллега',
        'behavior': {'interests': [' сохранить репутацию ', 'получить ясный план']},
    }

    private = builder.build(
        session=session, mission=mission, character=character,
        paei_profile={'leading_letter': 'P', 'prompt_rules': 'Скрытые правила P'},
        rules={'critical_error_limit': 2},
    )
    public = builder.build_frontend_context(game_context=private)

    assert private['interests'] == ['сохранить репутацию', 'получить ясный план']
    assert private['mission']['context']['hidden_context'] == 'Секрет: он не понял требования'
    assert private['rules'] == {'critical_error_limit': 2}
    assert public['mission']['public_context'] == 'Коллега задерживает задачу'
    assert public['character']['name'] == 'Игорь'
    public_text = json.dumps(public, ensure_ascii=False)
    assert 'Секрет' not in public_text
    assert 'сохранить репутацию' not in public_text
    assert 'Скрытые правила P' not in public_text
    assert 'critical_error_limit' not in public_text

    private['mission']['context']['hidden_context'] = 'изменено'
    assert mission['context']['hidden_context'] == 'Секрет: он не понял требования'
    malformed = builder.build(
        session={'state': 'invalid'},
        mission={'context': 'invalid'},
        character={'behavior': 'invalid'},
    )
    assert malformed['interests'] == []
    assert malformed['state']['contact'] == 0


def test_history_uses_recent_completed_dialogue_with_a_character_budget():
    builder = ContextBuilder(max_history_messages=3, max_history_chars=10)
    messages = [
        {'role': 'system', 'content': 'secret'},
        {'role': 'user', 'content': 'old'},
        {'role': 'assistant', 'content': '123456'},
        {'role': 'user', 'content': '123456789'},
        {'role': 'assistant', 'content': 'pending', 'processing_status': 'pending'},
    ]
    first = builder.build(session={}, messages=messages)
    second = builder.build(session={}, messages=messages)

    assert first == second
    assert first['history'] == [{'role': 'user', 'content': '123456789'}]
    assert sum(len(row['content']) for row in first['history']) <= 10

    oversized = builder.build(
        session={}, messages=[{'role': 'user', 'content': 'abcdefghi'}],
    )
    assert oversized['history'] == [{'role': 'user', 'content': 'abcdefghi'}]
    short_builder = ContextBuilder(max_history_chars=5)
    shortened = short_builder.build(
        session={}, messages=[{'role': 'user', 'content': 'abcdefghi'}],
    )
    assert shortened['history'] == [{'role': 'user', 'content': '…fghi'}]


def test_opponent_receives_bounded_context_and_current_message_once():
    builder = ContextBuilder(max_history_messages=2, max_history_chars=8)
    game_context = builder.build(
        session={'state': {'contact': 70}},
        mission={'context': {'hidden_context': 'Секрет для персонажа'}},
        messages=[
            {'role': 'assistant', 'content': 'старый ответ'},
            {'role': 'user', 'content': 'вопрос'},
            {'role': 'assistant', 'content': 'ответ'},
        ],
    )
    opponent_context = builder.build_opponent_context(
        game_context=game_context, evaluation={'intent': 'question'},
    )
    messages = GameService._build_opponent_messages(
        context=opponent_context, player_message='новый вопрос', final=False,
    )

    private_payload = json.loads(messages[1]['content'])
    assert private_payload['game']['mission']['context']['hidden_context'] == 'Секрет для персонажа'
    assert 'history' not in private_payload['game']
    assert messages[2:-1] == game_context['history']
    assert messages[-1] == {'role': 'user', 'content': 'новый вопрос'}


def test_public_message_schema_excludes_internal_evaluation_and_payload():
    public_message = SessionMessageResponse.model_validate({
        'id': UUID(int=1),
        'session_id': UUID(int=2),
        'sequence_number': 1,
        'role': 'user',
        'content': 'Привет',
        'processing_status': 'completed',
        'created_at': datetime(2026, 9, 25, tzinfo=UTC),
        'evaluation': {'hidden_reason': 'Внутренний вывод'},
        'payload': {'secret': 'Скрытый факт'},
    }).model_dump(mode='json')

    assert public_message['content'] == 'Привет'
    assert 'evaluation' not in public_message
    assert 'payload' not in public_message
