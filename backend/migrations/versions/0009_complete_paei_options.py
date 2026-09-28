"""Make all four PAEI styles available when authoring characters."""

from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO paei_profiles(code, leading_letter, p_value, a_value, e_value, i_value, prompt_rules)
        VALUES
          ('DEMO_P', 'P', 85, 45, 45, 45, 'Ориентируется на результат, срок и следующий конкретный шаг.'),
          ('DEMO_E', 'E', 45, 35, 85, 50, 'Ищет возможности и новые варианты, прежде чем закрепить план.')
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade():
    # Profiles may already be referenced by authored characters and sessions.
    pass
