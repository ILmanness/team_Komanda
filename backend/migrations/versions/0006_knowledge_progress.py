"""Persist reading progress and short knowledge checks."""

from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE knowledge_progress (
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            knowledge_item_id uuid NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            completed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, knowledge_item_id)
        )
    """)
    op.execute("""
        CREATE TABLE knowledge_quiz_attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            knowledge_item_id uuid NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            answers jsonb NOT NULL,
            score smallint NOT NULL CHECK (score >= 0),
            question_count smallint NOT NULL CHECK (question_count > 0),
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_quiz_attempts_user_item
        ON knowledge_quiz_attempts(user_id, knowledge_item_id, created_at DESC)
    """)


def downgrade():
    op.execute('DROP TABLE knowledge_quiz_attempts')
    op.execute('DROP TABLE knowledge_progress')
