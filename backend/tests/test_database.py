"""Run with RUN_DB_TESTS=1. Only a uniquely named test schema is removed."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app import retention
from app.auth import dependencies as auth_dependencies
from app.auth.security import create_access_token
from app.config import Settings, get_settings
from app.game import service as game_service
from app.main import app
from app.sessions import router as sessions_router
from app.sessions import websocket as sessions_websocket

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL')


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
    engine = create_engine(get_settings().database_url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        migrate(engine, getattr(request, 'param', 'head'))
        monkeypatch.setattr(retention, 'engine', engine)
        monkeypatch.setattr(retention, 'get_settings', lambda: Settings(
            _env_file=None, history_retention_days=7, session_retention_days=30,
            active_session_idle_days=30))
        yield engine
    finally:
        engine.dispose()
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


def test_retention_dry_run_and_apply(database):
    with database.begin() as connection:
        active = create_session(connection)
        old = create_session(connection, days=8)
        expired = create_session(connection, days=31)
        idle = create_session(connection, idle_days=31)
    expected = {'abandoned': 1, 'histories_purged': 1, 'sessions_deleted': 1}
    assert retention.cleanup() == expected
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM game_sessions')).scalar() == 4
        assert connection.execute(text('SELECT count(*) FROM session_messages')).scalar() == 8
    assert retention.cleanup(apply=True) == expected
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM game_sessions WHERE id = :id'), {'id': expired}).scalar() == 0
        for session_id in (active, idle):
            assert connection.execute(text('SELECT count(*) FROM session_messages WHERE session_id = :id'), {'id': session_id}).scalar() == 2
        row = connection.execute(text('SELECT custom_context, memory_summary, history_purged_at FROM game_sessions WHERE id = :id'), {'id': old}).one()
        assert row[0] == row[1] == {} and row[2] is not None
    assert retention.cleanup(apply=True) == {'abandoned': 0, 'histories_purged': 0, 'sessions_deleted': 0}


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
        assert opponent['type'] == 'opponent.message', opponent
        assert socket.receive_json()['type'] == 'state.update'
    messages = client.get(f'/api/v1/sessions/{session_id}/messages', headers=headers)
    assert messages.status_code == 200
    assert [message['role'] for message in messages.json()['messages']] == ['user', 'assistant']
    finished = client.post(f'/api/v1/sessions/{session_id}/finish', headers=headers)
    assert finished.status_code == 200 and finished.json()['status'] == 'completed'


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
