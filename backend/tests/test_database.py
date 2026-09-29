"""Run with RUN_DB_TESTS=1. Only a uniquely named test schema is removed."""
import asyncio
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app import retention
from app.admin import router as admin_router
from app.ai import MockLLMProvider
from app.auth import dependencies as auth_dependencies
from app.auth import router as auth_router
from app.auth.security import create_access_token
from app.catalog import router as catalog_router
from app.config import Settings, get_settings
from app.game import service as game_service
from app.game.evaluator import Evaluator
from app.main import app
from app.sessions import router as sessions_router
from app.sessions import websocket as sessions_websocket
from app.users import router as users_router

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL')


class DualContext:
    """Use the same isolated schema from synchronous setup and async app code."""

    def __init__(self, sync_context, async_context):
        self.sync_context = sync_context
        self.async_context = async_context

    def __enter__(self):
        return self.sync_context.__enter__()

    def __exit__(self, *args):
        return self.sync_context.__exit__(*args)

    async def __aenter__(self):
        return await self.async_context.__aenter__()

    async def __aexit__(self, *args):
        return await self.async_context.__aexit__(*args)


class DatabasePair:
    def __init__(self, sync_engine, async_engine):
        self.sync_engine = sync_engine
        self.async_engine = async_engine

    def begin(self):
        return DualContext(self.sync_engine.begin(), self.async_engine.begin())

    def connect(self):
        return DualContext(self.sync_engine.connect(), self.async_engine.connect())


def migrate(engine, revision='head', downgrade=False):
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        if downgrade:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)


@pytest.fixture
def database(monkeypatch, request):
    schema = 'arena_test_' + uuid4().hex
    admin = create_engine(get_settings().database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    connect_args = {'options': f'-csearch_path={schema}'}
    sync_engine = create_engine(get_settings().database_url, connect_args=connect_args)
    async_engine = create_async_engine(
        get_settings().database_url, connect_args=connect_args, poolclass=NullPool,
    )
    engine = DatabasePair(sync_engine, async_engine)
    try:
        migrate(engine, getattr(request, 'param', 'head'))
        monkeypatch.setattr(retention, 'engine', engine)
        monkeypatch.setattr(retention, 'get_settings', lambda: Settings(
            _env_file=None, history_retention_days=7, session_retention_days=30,
            active_session_idle_days=30))
        yield engine
    finally:
        asyncio.run(async_engine.dispose())
        sync_engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def create_session(connection, days=None, idle_days=0):
    user_id = connection.execute(text("INSERT INTO users(display_name) VALUES ('test') RETURNING id")).scalar_one()
    session_id = connection.execute(text('''
        INSERT INTO game_sessions(user_id, mode, custom_context, status, started_at, completed_at, last_activity_at)
        VALUES (:user, 'custom', '{"private":"secret"}', :status,
            now() - interval '90 days',
            CASE WHEN CAST(:days AS integer) IS NOT NULL THEN now() - make_interval(days => :days) END,
            now() - make_interval(days => :idle)) RETURNING id
    '''), {'user': user_id, 'status': 'active' if days is None else 'completed',
           'days': days, 'idle': idle_days}).scalar_one()
    message_id = connection.execute(text('''
        INSERT INTO session_messages(session_id, sequence_number, role, content, idempotency_key, processing_status)
        VALUES (:id, 1, 'user', 'private text', :key, 'completed') RETURNING id
    '''), {'id': session_id, 'key': uuid4()}).scalar_one()
    connection.execute(text('''
        INSERT INTO session_messages(session_id, sequence_number, role, content, processing_status, reply_to_message_id)
        VALUES (:id, 2, 'assistant', 'reply', 'completed', :reply)
    '''), {'id': session_id, 'reply': message_id})
    return session_id


def test_hint_endpoint_limits_one_per_turn_and_records_penalty(database, monkeypatch):
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    with database.begin() as connection:
        session_id = create_session(connection)
        user_id = connection.execute(text(
            'SELECT user_id FROM game_sessions WHERE id = :id'
        ), {'id': session_id}).scalar_one()
        message = 'Давайте обсудим, как можем найти решение.'
        evaluation = asyncio.run(Evaluator(MockLLMProvider(demo_evaluation=True)).evaluate(
            context={}, player_message=message,
        ))
        connection.execute(text("""
            UPDATE game_sessions
            SET state = :state, config_snapshot = :snapshot
            WHERE id = :id
        """), {
            'id': session_id,
            'state': Jsonb({
                'turn': 1, 'contact': 8, 'tension': 0, 'progress': 12,
                'critical_errors': 0, 'negotiation_quality': 62,
            }),
            'snapshot': Jsonb({
                'mission': {'task': 'Согласовать план'},
                'difficulty': {'code': 'Normal'},
            }),
        })
        connection.execute(text("""
            UPDATE session_messages
            SET content = :content, evaluation = :evaluation
            WHERE session_id = :id AND role = 'user'
        """), {
            'id': session_id,
            'content': message,
            'evaluation': Jsonb(evaluation),
        })

    client = TestClient(app)
    headers = {'Authorization': f'Bearer {create_access_token(user_id)}'}
    url = f'/api/v1/sessions/{session_id}/hint'
    first = client.post(url, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()['hints_used'] == 1
    assert first.json()['remaining'] == 2
    assert client.post(url, headers=headers).status_code == 409
    with database.connect() as connection:
        state = connection.execute(text(
            'SELECT state FROM game_sessions WHERE id = :id'
        ), {'id': session_id}).scalar_one()
    assert state['negotiation_quality'] == 59
    assert state['hint_history'] == [{
        'turn': 1, 'hint_type': 'strategy', 'level': 1,
    }]


def test_retention_dry_run_and_apply(database):
    with database.begin() as connection:
        active = create_session(connection)
        old = create_session(connection, days=8)
        expired = create_session(connection, days=31)
        idle = create_session(connection, idle_days=31)
    expected = {'abandoned': 1, 'histories_purged': 1, 'sessions_deleted': 1}
    assert asyncio.run(retention.cleanup()) == expected
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM game_sessions')).scalar() == 4
        assert connection.execute(text('SELECT count(*) FROM session_messages')).scalar() == 8
    assert asyncio.run(retention.cleanup(apply=True)) == expected
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM game_sessions WHERE id = :id'), {'id': expired}).scalar() == 0
        for session_id in (active, idle):
            assert connection.execute(text('SELECT count(*) FROM session_messages WHERE session_id = :id'), {'id': session_id}).scalar() == 2
        row = connection.execute(text('SELECT custom_context, memory_summary, history_purged_at FROM game_sessions WHERE id = :id'), {'id': old}).one()
        assert row[0] == row[1] == {} and row[2] is not None
    assert asyncio.run(retention.cleanup(apply=True)) == {'abandoned': 0, 'histories_purged': 0, 'sessions_deleted': 0}


def test_duplicate_message_rejected(database):
    with database.begin() as connection:
        session_id = create_session(connection)
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(text('''
            INSERT INTO session_messages(session_id, sequence_number, role, content)
            VALUES (:id, 1, 'assistant', 'duplicate')
        '''), {'id': session_id})


def test_story_without_storyline_rejected(database):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(text("INSERT INTO missions(mission_type, interaction_type, title, task) VALUES ('story', 'ai_dialogue', 'bad', 'bad')"))


def test_game_custom_session_websocket_round_trip(database, monkeypatch):
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(sessions_websocket, 'engine', database)
    monkeypatch.setattr(game_service, 'engine', database)
    monkeypatch.setattr(
        sessions_websocket, 'game_service',
        game_service.GameService(provider=MockLLMProvider(demo_evaluation=True)),
    )
    with database.begin() as connection:
        user_id = connection.execute(text("INSERT INTO users(display_name) VALUES ('Player') RETURNING id")).scalar_one()
    token = create_access_token(user_id)
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {token}'}
    created = client.post('/api/v1/sessions', headers=headers, json={
        'mode': 'custom', 'custom_context': {
            'situation': 'Команда обсуждает срок проекта.',
            'player_role': 'Руководитель', 'opponent_role': 'Заказчик',
            'goal': 'Согласовать новый срок.',
        },
    })
    assert created.status_code == 201, created.text
    session_id = created.json()['id']
    assert client.get(f'/api/v1/sessions/{session_id}', headers=headers).status_code == 200
    with client.websocket_connect(f'/api/v1/ws/sessions/{session_id}?token={token}') as socket:
        assert socket.receive_json()['type'] == 'session.connected'
        socket.send_json({'type': 'player.message', 'idempotency_key': str(uuid4()), 'content': 'Давайте обсудим сроки.'})
        assert socket.receive_json()['type'] == 'message.accepted'
        opponent = socket.receive_json()
        while opponent['type'] == 'opponent.delta':
            opponent = socket.receive_json()
        assert opponent['type'] == 'opponent.message', opponent
        assert opponent['emotion'] == 'warm', opponent
        state = socket.receive_json()
        assert state['type'] == 'state.update' and state['state']['progress'] == 0
    messages = client.get(f'/api/v1/sessions/{session_id}/messages', headers=headers)
    assert messages.status_code == 200
    assert [message['role'] for message in messages.json()['messages']] == ['user', 'assistant']
    assert messages.json()['messages'][1]['emotion'] == 'warm'
    assert 'payload' not in messages.json()['messages'][1]
    assert 'evaluation' not in messages.json()['messages'][1]
    finished = client.post(f'/api/v1/sessions/{session_id}/finish', headers=headers)
    assert finished.status_code == 200 and finished.json()['status'] == 'completed'
    assert finished.json()['final_result']['result'] == 'finished'


def test_opponent_failure_does_not_apply_partial_turn(database, monkeypatch):
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(game_service, 'engine', database)
    with database.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Player') RETURNING id"
        )).scalar_one()
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {create_access_token(user_id)}'}
    created = client.post('/api/v1/sessions', headers=headers, json={
        'mode': 'custom', 'custom_context': {
            'situation': 'Переговоры о сроке.', 'player_role': 'Менеджер',
            'opponent_role': 'Заказчик', 'goal': 'Согласовать срок.',
        },
    })
    assert created.status_code == 201, created.text
    session_id = created.json()['id']
    with database.connect() as connection:
        before = connection.execute(text('''
            SELECT state, memory_summary FROM game_sessions WHERE id = :id
        '''), {'id': session_id}).one()

    class FailingOpponent(MockLLMProvider):
        async def generate(self, messages):
            raise RuntimeError('model unavailable')

    service = game_service.GameService(provider=FailingOpponent(demo_evaluation=True))
    turn = asyncio.run(service.process_player_message(
        session_id=UUID(session_id), user_id=user_id,
        content='Давайте обсудим сроки.', idempotency_key=uuid4(),
    ))
    assert turn['events'][-1]['code'] == 'opponent_failed'
    with database.connect() as connection:
        after = connection.execute(text('''
            SELECT state, memory_summary FROM game_sessions WHERE id = :id
        '''), {'id': session_id}).one()
        messages = connection.execute(text('''
            SELECT role, processing_status, evaluation FROM session_messages
            WHERE session_id = :id ORDER BY sequence_number
        '''), {'id': session_id}).all()
    assert after == before
    assert messages == [('user', 'failed', None)]


def test_memory_survives_service_reload(database, monkeypatch):
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(game_service, 'engine', database)
    with database.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Player') RETURNING id"
        )).scalar_one()
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {create_access_token(user_id)}'}
    created = client.post('/api/v1/sessions', headers=headers, json={
        'mode': 'custom', 'custom_context': {
            'situation': 'Переговоры о сроке.', 'player_role': 'Менеджер',
            'opponent_role': 'Заказчик', 'goal': 'Согласовать срок.',
        },
    })
    assert created.status_code == 201, created.text
    session_id = UUID(created.json()['id'])
    message = 'Релиз в пятницу. Договорились проверить сборку утром?'
    evaluation = {
        'schema_version': 'ai10-v1', 'intent': 'agreement',
        'observations': {'conversation_progress': 'forward', 'features': [
            {'code': 'fact_statement', 'evidence': 'Релиз в пятницу.'},
            {'code': 'agreement_fixation', 'evidence': 'Договорились проверить сборку утром?'},
        ]},
        'profile_fit': {'P': 1, 'A': 1, 'E': 0, 'I': 0},
        'proposed_event': {'action_type': 'positive', 'critical_flags': []},
        'explanation': {'reason': 'Конкретное предложение'},
        'paei_markers': [], 'hint_basis': [],
    }
    service = game_service.GameService(provider=MockLLMProvider(demo_evaluation=True))
    turn = asyncio.run(service.process_player_message(
        session_id=session_id, user_id=user_id, content=message,
        idempotency_key=uuid4(), evaluation_override=evaluation,
        response_override='Согласен, проверим сборку утром.',
    ))
    assert turn['events'][1]['type'] == 'opponent.message'
    reloaded = game_service.GameService(provider=MockLLMProvider(demo_evaluation=True))
    saved = asyncio.run(reloaded._get_session(session_id=session_id, user_id=user_id))
    assert saved['memory_summary']['agreements'][0]['text'] == (
        'Договорились проверить сборку утром?'
    )
    assert saved['state']['memory']['facts'][0]['text'] == 'Релиз в пятницу.'


@pytest.mark.parametrize('message', ['бууббууб', 'ты балбес'])
def test_non_negotiation_input_completes_turn_with_character_reply(database, monkeypatch, message):
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(game_service, 'engine', database)
    with database.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Player') RETURNING id"
        )).scalar_one()
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {create_access_token(user_id)}'}
    created = client.post('/api/v1/sessions', headers=headers, json={
        'mode': 'custom', 'custom_context': {
            'situation': 'Согласование срока.', 'player_role': 'Заказчик',
            'opponent_role': 'Руководитель проекта', 'opponent_name': 'Анна',
            'goal': 'Договориться о сроке.',
        },
    })
    assert created.status_code == 201, created.text

    class NoCallProvider(MockLLMProvider):
        async def generate(self, messages):
            raise AssertionError('No model call expected for this input')

        async def generate_structured(self, messages, response_model):
            raise AssertionError('No model call expected for this input')

    service = game_service.GameService(provider=NoCallProvider())
    turn = asyncio.run(service.process_player_message(
        session_id=UUID(created.json()['id']), user_id=user_id,
        content=message, idempotency_key=uuid4(),
    ))
    assert [event['type'] for event in turn['events'][:3]] == [
        'message.accepted', 'opponent.message', 'state.update',
    ]
    assert turn['events'][1]['content'].startswith(('Я ', 'Мне '))
    assert 'запрос' not in turn['events'][1]['content'].casefold()
    assert turn['events'][2]['state']['turn'] == 1


def test_assistant_style_model_reply_is_replaced_before_saving(database, monkeypatch):
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    monkeypatch.setattr(sessions_router, 'engine', database)
    monkeypatch.setattr(game_service, 'engine', database)
    with database.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Player') RETURNING id"
        )).scalar_one()
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {create_access_token(user_id)}'}
    created = client.post('/api/v1/sessions', headers=headers, json={
        'mode': 'custom', 'custom_context': {
            'situation': 'Согласование срока.', 'player_role': 'Заказчик',
            'opponent_role': 'Руководитель проекта', 'opponent_name': 'Анна',
            'goal': 'Договориться о сроке.',
        },
    })
    assert created.status_code == 201, created.text
    session_id = UUID(created.json()['id'])
    service = game_service.GameService(provider=MockLLMProvider(
        text_response='Не понял вас, повторите запрос? Нужны конкретные ответы.',
    ))
    evaluation = {
        'schema_version': 'ai10-v1', 'intent': 'question',
        'observations': {'conversation_progress': 'forward', 'features': [
            {'code': 'clarification', 'evidence': 'Какие условия вам подходят?'},
        ]},
        'profile_fit': {'P': 0, 'A': 0, 'E': 0, 'I': 0},
        'proposed_event': {'action_type': 'positive', 'critical_flags': []},
        'explanation': {'reason': 'Уточнение условий'},
        'paei_markers': [], 'hint_basis': [],
    }
    turn = asyncio.run(service.process_player_message(
        session_id=session_id, user_id=user_id,
        content='Какие условия вам подходят?', idempotency_key=uuid4(),
        evaluation_override=evaluation,
    ))
    reply = turn['events'][1]['content']
    assert reply.startswith('Мне ')
    assert 'запрос' not in reply.casefold()
    with database.connect() as connection:
        stored = connection.execute(text('''
            SELECT content FROM session_messages
            WHERE session_id=:sid AND role='assistant'
        '''), {'sid': session_id}).scalar_one()
    assert stored == reply


def test_story_unlock_requires_success_and_manual_finish_does_not_unlock(database, monkeypatch):
    for module in (auth_dependencies, catalog_router, sessions_router, users_router, game_service):
        monkeypatch.setattr(module, 'engine', database)
    with database.begin() as connection:
        user_id = connection.execute(text("INSERT INTO users(display_name) VALUES ('Player') RETURNING id")).scalar_one()
        storyline_id = connection.execute(text('''
            INSERT INTO storylines(slug, title, status) VALUES ('demo', 'Demo', 'published') RETURNING id
        ''')).scalar_one()
        character_id = connection.execute(text('''
            INSERT INTO characters(slug, name) VALUES ('anna', 'Anna') RETURNING id
        ''')).scalar_one()
        paei_id = connection.execute(text('''
            INSERT INTO paei_profiles(code, leading_letter, p_value, a_value, e_value, i_value)
            VALUES ('TEST', 'P', 50, 50, 50, 50) RETURNING id
        ''')).scalar_one()
        difficulty_id = connection.execute(text('''
            INSERT INTO difficulty_profiles(code, title) VALUES ('TEST', 'Test') RETURNING id
        ''')).scalar_one()
        mission_ids = []
        for order in (1, 2):
            mission_ids.append(connection.execute(text('''
                INSERT INTO missions(storyline_id, character_id, mission_type, interaction_type,
                                     branch_key, order_index, title, task, status)
                VALUES (:storyline, :character, 'story', 'ai_dialogue', 'main', :order,
                        :title, 'Согласовать срок на пятницу', 'published') RETURNING id
            '''), {'storyline': storyline_id, 'character': character_id,
                   'order': order, 'title': f'Mission {order}'}).scalar_one())
    token = create_access_token(user_id)
    headers = {'Authorization': f'Bearer {token}'}
    client = TestClient(app)
    progress_url = f'/api/v1/storylines/{storyline_id}/progress'
    progress = client.get(progress_url, headers=headers)
    assert progress.status_code == 200
    assert [(item['unlocked'], item['completed']) for item in progress.json()['missions']] == [
        (True, False), (False, False),
    ]
    def request(mission_id):
        return client.post('/api/v1/sessions', headers=headers, json={
            'mode': 'story', 'mission_id': str(mission_id),
            'paei_profile_id': str(paei_id), 'difficulty_profile_id': str(difficulty_id),
        })
    assert request(mission_ids[1]).status_code == 403
    first = request(mission_ids[0])
    assert first.status_code == 201, first.text
    finished = client.post(f"/api/v1/sessions/{first.json()['id']}/finish", headers=headers)
    assert finished.json()['final_result']['result'] == 'failure'
    assert request(mission_ids[1]).status_code == 403
    second_attempt = request(mission_ids[0])
    player_message = 'Давайте согласуем срок на пятницу.'
    opponent_message = 'Да, согласна на пятницу.'
    service = game_service.GameService(provider=MockLLMProvider(
        demo_evaluation=True,
        structured_response={
            'status': 'achieved', 'progress': 100, 'reason': 'Срок согласован.',
            'evidence': [
                {'speaker': 'player', 'quote': player_message},
                {'speaker': 'opponent', 'quote': opponent_message},
            ],
        },
    ))
    turn = asyncio.run(service.process_player_message(
        session_id=second_attempt.json()['id'], user_id=user_id,
        content=player_message, idempotency_key=uuid4(),
        response_override=opponent_message,
    ))
    assert turn['events'][-1]['final_result']['result'] == 'success'
    progress = client.get(progress_url, headers=headers).json()['missions']
    assert [(item['unlocked'], item['completed']) for item in progress] == [
        (True, True), (True, False),
    ]
    assert request(mission_ids[1]).status_code == 201
    with database.begin() as connection:
        connection.execute(text('''
            UPDATE game_sessions SET started_at=now() - interval '32 days',
                                     completed_at=now() - interval '31 days'
            WHERE id=:id
        '''), {'id': second_attempt.json()['id']})
    asyncio.run(retention.cleanup(apply=True))
    assert client.get(progress_url, headers=headers).json()['missions'][1]['unlocked'] is True
    stats = client.get('/api/v1/users/me/stats', headers=headers)
    assert stats.status_code == 200 and stats.json()['story_successes'] == 1
    updated = client.patch('/api/v1/users/me', headers=headers, json={'display_name': 'New Player'})
    assert updated.status_code == 200 and updated.json()['display_name'] == 'New Player'


def test_registration_has_login_and_display_name(database, monkeypatch):
    monkeypatch.setattr(auth_router, 'engine', database)
    monkeypatch.setattr(auth_dependencies, 'engine', database)
    client = TestClient(app)
    registered = client.post('/api/v1/auth/register', json={
        'login': 'captain', 'email': 'captain@example.com',
        'display_name': 'Капитан', 'password': 'long-password-123',
    })
    assert registered.status_code == 201, registered.text
    assert registered.json()['user']['login'] == 'captain'
    assert registered.json()['user']['display_name'] == 'Капитан'
    assert client.post('/api/v1/auth/login', json={
        'login': 'captain', 'password': 'long-password-123',
    }).status_code == 200
    assert client.post('/api/v1/auth/login', json={
        'login': 'captain@example.com', 'password': 'long-password-123',
    }).status_code == 200
    assert client.post('/api/v1/auth/register', json={
        'login': 'CAPTAIN', 'email': 'other@example.com',
        'display_name': 'Other', 'password': 'long-password-123',
    }).status_code == 409


def test_admin_training_choice_is_private_and_playable(database, monkeypatch):
    for module in (auth_dependencies, admin_router, catalog_router, sessions_router,
                   sessions_websocket, game_service):
        monkeypatch.setattr(module, 'engine', database)
    with database.begin() as connection:
        admin_id = connection.execute(text(
            "INSERT INTO users(display_name, role) VALUES ('Admin', 'admin') RETURNING id"
        )).scalar_one()
        player_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Player') RETURNING id"
        )).scalar_one()
        paei_id = connection.execute(text('''
            INSERT INTO paei_profiles(code, leading_letter, p_value, a_value, e_value, i_value)
            VALUES ('TEST', 'P', 50, 50, 50, 50) RETURNING id
        ''')).scalar_one()
        difficulty_id = connection.execute(text('''
            INSERT INTO difficulty_profiles(code, title, settings)
            VALUES ('TEST', 'Test', :settings) RETURNING id
        '''), {'settings': '{"max_turns":20}'}).scalar_one()
    client = TestClient(app)
    admin_headers = {'Authorization': f'Bearer {create_access_token(admin_id)}'}
    player_token = create_access_token(player_id)
    player_headers = {'Authorization': f'Bearer {player_token}'}
    assert client.get('/api/v1/admin/overview', headers=player_headers).status_code == 403
    character = client.post('/api/v1/admin/characters', headers=admin_headers, json={
        'slug': 'test-anna', 'name': 'Анна', 'role_title': 'Коллега',
        'description': 'Задаёт вопросы', 'base_prompt': 'Будь спокойной',
    })
    assert character.status_code == 201, character.text
    knowledge = client.post('/api/v1/admin/knowledge', headers=admin_headers, json={
        'slug': 'test-topic', 'title': 'Разговор о сроках', 'item_type': 'topic',
        'summary': 'Про сроки', 'body': 'Материал',
    })
    assert knowledge.status_code == 201, knowledge.text
    topic_id = knowledge.json()['id']
    assert client.put(f'/api/v1/admin/knowledge/{topic_id}/status', headers=admin_headers,
                      json={'status': 'published'}).status_code == 200
    mission = client.post('/api/v1/admin/missions', headers=admin_headers, json={
        'mission_type': 'method_training', 'interaction_type': 'single_choice',
        'knowledge_item_id': topic_id, 'character_id': character.json()['id'],
        'title': 'Сорванный срок', 'situation': 'Команда опаздывает с релизом.',
        'task': 'Выберите ответ', 'opening_message': 'Что со сроком?',
        'hints': ['Признайте проблему'],
        'choices': [
            {'id': 'good', 'text': 'Обсудим новый план', 'feedback': 'Хороший ход',
             'quality': .9, 'progress': 70},
            {'id': 'bad', 'text': 'Это не моя проблема', 'feedback': 'Плохой ход',
             'quality': .1, 'progress': 5},
        ],
    })
    assert mission.status_code == 201, mission.text
    mission_id = mission.json()['id']
    assert client.put(f'/api/v1/admin/missions/{mission_id}/status', headers=admin_headers,
                      json={'status': 'published'}).status_code == 200
    public = client.get(f'/api/v1/missions/{mission_id}').json()
    assert 'config' not in public and 'context' not in public
    assert public['choices'] == [{'id': 'good', 'text': 'Обсудим новый план'},
                                 {'id': 'bad', 'text': 'Это не моя проблема'}]
    session = client.post('/api/v1/sessions', headers=player_headers, json={
        'mode': 'method_training', 'mission_id': mission_id,
        'paei_profile_id': str(paei_id), 'difficulty_profile_id': str(difficulty_id),
    })
    assert session.status_code == 201, session.text
    session_id = session.json()['id']
    with client.websocket_connect(f'/api/v1/ws/sessions/{session_id}?token={player_token}') as socket:
        assert socket.receive_json()['type'] == 'session.connected'
        socket.send_json({'type': 'player.choice', 'choice_id': 'good',
                          'idempotency_key': str(uuid4())})
        events = [socket.receive_json() for _ in range(4)]
        assert [event['type'] for event in events] == [
            'message.accepted', 'opponent.message', 'state.update', 'game.finished',
        ], events
        assert events[-1]['final_result']['result'] == 'success'
    assert client.get(f'/api/v1/sessions/{session_id}', headers=player_headers).json()['status'] == 'completed'


@pytest.mark.parametrize('database', ['0001'], indirect=True)
def test_upgrade_from_catalog_branch_preserves_password_hash(database):
    with database.begin() as connection:
        connection.execute(text('ALTER TABLE users ADD COLUMN password_hash varchar(128)'))
        user_id = connection.execute(text(
            "INSERT INTO users(display_name, password_hash) VALUES ('Existing', 'existing-hash') RETURNING id"
        )).scalar_one()
    migrate(database)
    with database.connect() as connection:
        assert connection.execute(text('SELECT password_hash FROM users WHERE id = :id'),
                                  {'id': user_id}).scalar_one() == 'existing-hash'
        assert connection.execute(text('''
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'users'
              AND column_name = 'password_hash'
        ''')).scalar_one() == 'text'


@pytest.mark.parametrize('database', ['0001'], indirect=True)
def test_password_migration_preserves_existing_users(database):
    with database.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO users(display_name) VALUES ('Existing user') RETURNING id"
        )).scalar_one()
    migrate(database)
    with database.begin() as connection:
        row = connection.execute(text(
            'SELECT display_name, password_hash FROM users WHERE id = :id'
        ), {'id': user_id}).one()
        assert tuple(row) == ('Existing user', None)
        # Only storage is tested here; no authentication is implemented yet.
        connection.execute(text('UPDATE users SET password_hash = :hash WHERE id = :id'),
                           {'hash': 'test-encoded-hash', 'id': user_id})
    migrate(database, 'head')  # Repeated upgrade is safe and keeps credentials.
    with database.connect() as connection:
        assert connection.execute(text('SELECT password_hash FROM users WHERE id = :id'),
                                  {'id': user_id}).scalar_one() == 'test-encoded-hash'
    migrate(database, '0001', downgrade=True)
    with database.connect() as connection:
        assert connection.execute(text('SELECT display_name FROM users WHERE id = :id'),
                                  {'id': user_id}).scalar_one() == 'Existing user'
        assert connection.execute(text('''
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'users'
              AND column_name = 'password_hash'
        ''')).scalar_one() == 0
