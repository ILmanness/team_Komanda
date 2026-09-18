"""Run with RUN_DB_TESTS=1. Only a uniquely named test schema is removed."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app import retention
from app.config import Settings, get_settings

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL')


@pytest.fixture
def database(monkeypatch):
    schema = 'arena_test_' + uuid4().hex
    admin = create_engine(get_settings().database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(get_settings().database_url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        sql = (Path(__file__).parents[1] / 'migrations/versions/0001_initial.sql').read_text()
        with engine.begin() as connection:
            for statement in sql.split(';'):
                if statement.strip():
                    connection.execute(text(statement))
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
