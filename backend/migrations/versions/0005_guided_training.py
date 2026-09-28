"""Allow the workbook's multi-step guided training format."""

from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE missions DROP CONSTRAINT missions_interaction_type_check')
    op.execute("""ALTER TABLE missions ADD CONSTRAINT missions_interaction_type_check
        CHECK (interaction_type IN ('ai_dialogue', 'scripted_dialogue', 'single_choice', 'guided_training'))""")
    op.execute('ALTER TABLE game_sessions DROP CONSTRAINT game_sessions_status_check')
    op.execute("""ALTER TABLE game_sessions ADD CONSTRAINT game_sessions_status_check
        CHECK (status IN ('active', 'completed', 'failed', 'abandoned', 'needs_review'))""")


def downgrade():
    op.execute('ALTER TABLE game_sessions DROP CONSTRAINT game_sessions_status_check')
    op.execute("""ALTER TABLE game_sessions ADD CONSTRAINT game_sessions_status_check
        CHECK (status IN ('active', 'completed', 'failed', 'abandoned'))""")
    op.execute('ALTER TABLE missions DROP CONSTRAINT missions_interaction_type_check')
    op.execute("""ALTER TABLE missions ADD CONSTRAINT missions_interaction_type_check
        CHECK (interaction_type IN ('ai_dialogue', 'scripted_dialogue', 'single_choice'))""")
