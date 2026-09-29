import argparse
import json
import logging
import time
import asyncio

from sqlalchemy import text

from app.config import get_settings
from app.db import engine

BATCH_SIZE = 200
logger = logging.getLogger(__name__)


async def cleanup(apply: bool = False) -> dict[str, int]:
    settings = get_settings()
    counts = {'abandoned': 0, 'histories_purged': 0, 'sessions_deleted': 0, 'tokens_purged': 0}
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            if not (await connection.execute(text('SELECT pg_try_advisory_xact_lock(18092026)'))).scalar():
                await transaction.rollback()
                return counts
            idle = (await connection.execute(text('''
                SELECT id FROM game_sessions
                WHERE status = 'active'
                  AND last_activity_at < now() - make_interval(days => :days)
                ORDER BY last_activity_at LIMIT :batch FOR UPDATE SKIP LOCKED
            '''), {'days': settings.active_session_idle_days, 'batch': BATCH_SIZE})).scalars().all()
            for session_id in idle:
                await connection.execute(text('''
                    UPDATE game_sessions SET status = 'abandoned', completed_at = now(),
                        lock_version = lock_version + 1 WHERE id = :id
                '''), {'id': session_id})
            counts['abandoned'] = len(idle)

            expired = (await connection.execute(text('''
                SELECT id FROM game_sessions WHERE status <> 'active'
                  AND completed_at <= now() - make_interval(days => :days)
                ORDER BY completed_at LIMIT :batch FOR UPDATE SKIP LOCKED
            '''), {'days': settings.session_retention_days, 'batch': BATCH_SIZE})).scalars().all()
            for session_id in expired:
                await connection.execute(text('DELETE FROM game_sessions WHERE id = :id'), {'id': session_id})
            counts['sessions_deleted'] = len(expired)

            histories = (await connection.execute(text('''
                SELECT id FROM game_sessions WHERE status <> 'active' AND history_purged_at IS NULL
                  AND completed_at <= now() - make_interval(days => :days)
                ORDER BY completed_at LIMIT :batch FOR UPDATE SKIP LOCKED
            '''), {'days': settings.history_retention_days, 'batch': BATCH_SIZE})).scalars().all()
            for session_id in histories:
                await connection.execute(text('DELETE FROM session_messages WHERE session_id = :id'), {'id': session_id})
                await connection.execute(text('''
                    UPDATE game_sessions SET state = '{}', memory_summary = '{}',
                        custom_context = CASE WHEN mode = 'custom' THEN '{}'::jsonb ELSE NULL END,
                        config_snapshot = '{}', history_purged_at = now(),
                        lock_version = lock_version + 1 WHERE id = :id
                '''), {'id': session_id})
            counts['histories_purged'] = len(histories)
            tokens = (await connection.execute(text('''
                DELETE FROM revoked_access_tokens WHERE token_hash IN (
                    SELECT token_hash FROM revoked_access_tokens WHERE expires_at < now()
                    ORDER BY expires_at LIMIT :batch FOR UPDATE SKIP LOCKED
                ) RETURNING token_hash
            '''), {'batch': BATCH_SIZE})).scalars().all()
            counts['tokens_purged'] = len(tokens)
            if apply:
                await transaction.commit()
            else:
                await transaction.rollback()
        except Exception:
            await transaction.rollback()
            raise
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Commit deletion; default is dry run')
    parser.add_argument('--loop', action='store_true', help='Repeat periodically')
    args = parser.parse_args()
    while True:
        try:
            print(json.dumps({'apply': args.apply, **asyncio.run(cleanup(args.apply))}), flush=True)
        except Exception:
            if not args.loop:
                raise
            logger.exception('Retention batch failed; next interval will retry')
        if not args.loop:
            break
        time.sleep(get_settings().retention_interval_seconds)
