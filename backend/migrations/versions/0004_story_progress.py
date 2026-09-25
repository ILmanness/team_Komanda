"""Keep completed story missions after session history is removed."""

from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE TABLE story_mission_progress (
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mission_id uuid NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
            completed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, mission_id)
        )
    ''')
    op.execute('''
        INSERT INTO story_mission_progress (user_id, mission_id, completed_at)
        SELECT user_id, mission_id, min(completed_at)
        FROM game_sessions
        WHERE mode = 'story' AND status = 'completed'
          AND final_result->>'result' = 'success'
        GROUP BY user_id, mission_id
        ON CONFLICT DO NOTHING
    ''')


def downgrade():
    op.execute('DROP TABLE story_mission_progress')
