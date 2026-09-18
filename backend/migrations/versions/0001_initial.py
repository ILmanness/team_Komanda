"""Nine application tables. SQL is kept readable for the whole team."""
from pathlib import Path

from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix('.sql').read_text(encoding='utf-8')
    # This migration contains plain statements, no procedural function bodies.
    for statement in sql.split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in ('session_messages', 'game_sessions', 'missions', 'difficulty_profiles',
                  'paei_profiles', 'characters', 'storylines', 'knowledge_items', 'users'):
        op.execute(f'DROP TABLE {table}')
