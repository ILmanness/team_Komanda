"""Allow authored branching method and principle trainings."""

from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE missions DROP CONSTRAINT missions_interaction_type_check')
    op.execute("""ALTER TABLE missions ADD CONSTRAINT missions_interaction_type_check
        CHECK (interaction_type IN ('ai_dialogue', 'scripted_dialogue', 'single_choice',
                                    'guided_training', 'branching_training'))""")


def downgrade():
    op.execute("UPDATE missions SET status='archived' WHERE interaction_type='branching_training'")
    op.execute('DELETE FROM missions WHERE interaction_type=\'branching_training\'')
    op.execute('ALTER TABLE missions DROP CONSTRAINT missions_interaction_type_check')
    op.execute("""ALTER TABLE missions ADD CONSTRAINT missions_interaction_type_check
        CHECK (interaction_type IN ('ai_dialogue', 'scripted_dialogue', 'single_choice',
                                    'guided_training'))""")
